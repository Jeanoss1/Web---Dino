"""Contadores por tipo de atracción: dinosaurios cuentan minutos; carros y motos, encendidos."""
from datetime import datetime, timedelta

from app.database import db
from app.models import Flota, RegistroUso
from tests.conftest import ADMIN, CAJERO_REAL, abrir_caja, sede, unidad, vencer_todo


def vender(cajero, u, bloques=1):
    return cajero.post('/caja/venta', data={'id_flota': u.id_flota, 'bloques': bloques, 'metodo_pago': 'efectivo'})


def contador(id_flota):
    db.session.expire_all()
    return db.session.get(Flota, id_flota).contador_sistema


def test_tipos_de_contador_por_defecto(app):
    tipos = {f.tipo: f.tipo_contador for f in Flota.query.all()}
    assert tipos == {'dinosaurio': 'minutos', 'carro': 'encendidos', 'moto': 'encendidos'}


def test_el_seed_deja_lecturas_de_ejemplo(app):
    for f in Flota.query.all():
        assert f.contador_sistema == 0                                    # el sistema recién empieza a contar
        if f.tipo_contador == 'minutos':
            assert 400 <= f.lectura_manual <= 700
        else:
            assert 1 <= f.lectura_manual <= 5


def test_carro_suma_un_encendido_al_iniciar_y_no_al_finalizar(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    carro = unidad('Real Plaza', 2)
    assert carro.tipo == 'carro'
    vender(cajero, carro, 3)                       # 3 bloques = un solo encendido
    assert contador(carro.id_flota) == 1           # sube al iniciar
    vencer_todo()
    assert contador(carro.id_flota) == 1           # no vuelve a subir al finalizar
    vender(cajero, carro)                          # se vuelve a prender
    assert contador(carro.id_flota) == 2


def test_moto_tambien_cuenta_encendidos(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    moto = unidad('Real Plaza', 3)
    vender(cajero, moto, 2)
    assert contador(moto.id_flota) == 1
    assert RegistroUso.query.one().contador_delta == 1


def test_dinosaurio_suma_minutos_al_finalizar_no_al_iniciar(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    dino = unidad('Real Plaza', 0)
    assert dino.tipo == 'dinosaurio'
    vender(cajero, dino, 3)                        # 36 minutos
    assert contador(dino.id_flota) == 0            # todavía no suma
    vencer_todo()
    assert contador(dino.id_flota) == 36           # suma bloques x 12 al finalizar
    vencer_todo()
    assert contador(dino.id_flota) == 36           # y no se duplica


def test_dinosaurio_finalizado_antes_suma_solo_los_minutos_reales(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    dino = unidad('Real Plaza', 0)
    vender(cajero, dino, 3)
    uso = RegistroUso.query.one()
    uso.hora_inicio = datetime.now() - timedelta(minutes=10)
    db.session.commit()
    cajero.post(f'/caja/uso/{uso.id_uso}/finalizar', data={'motivo': 'Se cansó'})
    assert contador(dino.id_flota) == 10


def test_el_administrador_configura_el_contador_de_cada_atraccion(app, como):
    admin = como(ADMIN)
    # una atraccion nueva de tipo "otros" elige como se cuenta
    admin.post('/admin/flota', data={'nombre': 'Trenecito', 'tipo': 'otros', 'id_sucursal': sede('Real Plaza').id_sucursal,
                                     'tipo_contador': 'encendidos', 'lectura_inicial': '7'})
    nuevo = Flota.query.filter_by(nombre='Trenecito').one()
    assert (nuevo.tipo_contador, nuevo.lectura_manual, nuevo.contador_sistema) == ('encendidos', 7, 0)

    # sin elegir, "otros" cuenta minutos; y se puede cambiar despues
    admin.post('/admin/flota', data={'nombre': 'Cohete', 'tipo': 'otros', 'id_sucursal': sede('Real Plaza').id_sucursal})
    cohete = Flota.query.filter_by(nombre='Cohete').one()
    assert cohete.tipo_contador == 'minutos'
    admin.post(f'/admin/flota/{cohete.id_flota}/contador', data={'tipo_contador': 'encendidos'})
    db.session.expire_all()
    assert db.session.get(Flota, cohete.id_flota).tipo_contador == 'encendidos'
    assert admin.post(f'/admin/flota/{cohete.id_flota}/contador', data={'tipo_contador': 'horas'}).status_code == 302
    db.session.expire_all()
    assert db.session.get(Flota, cohete.id_flota).tipo_contador == 'encendidos'


def test_solo_el_administrador_cambia_el_tipo_de_contador(app, como):
    r = como(CAJERO_REAL).post(f'/admin/flota/{unidad("Real Plaza").id_flota}/contador', data={'tipo_contador': 'encendidos'})
    assert r.status_code == 403
