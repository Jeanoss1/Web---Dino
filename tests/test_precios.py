from decimal import Decimal

import pytest

from app.database import db
from app.models import Tarifa, Venta
from app.services import tarifas
from app.services.errores import ErrorNegocio
from tests.conftest import ADMIN, CAJERO_REAL, abrir_caja, unidad


def test_tarifa_estandar_10_soles_por_12_minutos(app):
    t = tarifas.tarifa_vigente()
    assert t.precio == Decimal('10.00') and t.minutos == 12


@pytest.mark.parametrize('bloques,minutos,total', [(1, 12, '10.00'), (2, 24, '20.00'), (3, 36, '30.00'), (5, 60, '50.00')])
def test_calculo_de_minutos_y_total(app, bloques, minutos, total):
    r = tarifas.calcular(bloques)
    assert r['minutos'] == minutos
    assert r['total'] == Decimal(total)


@pytest.mark.parametrize('malo', [0, -1, 'abc', None, 999])
def test_bloques_invalidos(app, malo):
    with pytest.raises(ErrorNegocio):
        tarifas.calcular(malo)


def test_venta_presencial_calcula_con_la_tarifa(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    u = unidad('Real Plaza')
    cajero.post('/caja/venta', data={'id_flota': u.id_flota, 'bloques': 3, 'metodo_pago': 'efectivo'})
    venta = Venta.query.one()
    assert venta.total == Decimal('30.00')
    assert venta.minutos == 36
    assert venta.detalles[0].precio == Decimal('10.00') and venta.detalles[0].cantidad == 3


def test_el_cajero_no_puede_imponer_un_precio(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    u = unidad('Real Plaza')
    cajero.post('/caja/venta', data={'id_flota': u.id_flota, 'bloques': 1, 'metodo_pago': 'efectivo',
                                     'precio': '0.01', 'total': '0.01'})
    assert Venta.query.one().total == Decimal('10.00')


def test_solo_el_administrador_edita_la_tarifa(app, como):
    r = como(CAJERO_REAL).post('/admin/tarifas', data={'precio': '1', 'minutos': '1'})
    assert r.status_code == 403
    assert tarifas.tarifa_vigente().precio == Decimal('10.00')

    r = como(ADMIN).post('/admin/tarifas', data={'precio': '12.50', 'minutos': '15'})
    assert r.status_code == 302
    db.session.expire_all()
    t = tarifas.tarifa_vigente()
    assert (t.precio, t.minutos) == (Decimal('12.50'), 15)
    assert tarifas.calcular(2)['total'] == Decimal('25.00')
    assert tarifas.calcular(2)['minutos'] == 30
    assert Tarifa.query.count() == 1


def test_la_tarifa_rechaza_valores_invalidos(app, como):
    admin = como(ADMIN)
    for datos in ({'precio': '-5', 'minutos': '12'}, {'precio': 'abc', 'minutos': '12'},
                  {'precio': '10', 'minutos': '0'}, {'precio': '0', 'minutos': '12'}):
        admin.post('/admin/tarifas', data=datos)
    db.session.expire_all()
    t = tarifas.tarifa_vigente()
    assert (t.precio, t.minutos) == (Decimal('10.00'), 12)


def test_api_de_flota_publica_precio_y_minutos_de_la_tarifa(client):
    datos = client.get('/api/flota').get_json()
    assert datos and all(f['precio'] == 10.0 and f['minutos'] == 12 for f in datos)
    assert 'precio_hora' not in datos[0]
