"""Permisos por rol en TODAS las rutas protegidas."""
import pytest

from tests.conftest import (ADMIN, CAJERO_MEGA, CAJERO_REAL, CLIENTE1, abrir_caja,
                            franja_libre, imagen, unidad)

# (método, ruta, quién puede entrar)
RUTAS = [
    ('get', '/disponibilidad', {'cliente'}),
    ('get', '/mis-reservas', {'cliente'}),
    ('get', '/api/mis-reservas', {'cliente'}),
    ('get', '/caja', {'cajero'}),
    ('get', '/caja/venta', {'cajero'}),
    ('get', '/caja/uso', {'cajero'}),
    ('get', '/caja/validaciones', {'cajero', 'administrador'}),
    ('get', '/api/caja/reservas', {'cajero', 'administrador'}),
    ('get', '/reportes/dashboard', {'administrador'}),
    ('get', '/reportes/', {'administrador'}),
    ('get', '/reportes/cuadre', {'administrador'}),
    ('get', '/reportes/exportar/excel', {'administrador'}),
    ('get', '/admin/usuarios', {'administrador'}),
    ('get', '/admin/sedes', {'administrador'}),
    ('get', '/admin/flota', {'administrador'}),
    ('get', '/admin/tarifas', {'administrador'}),
    ('get', '/admin/turnos', {'administrador'}),
    ('get', '/admin/mantenimiento/', {'administrador'}),
    ('post', '/admin/tarifas', {'administrador'}),
    ('post', '/admin/usuarios', {'administrador'}),
    ('post', '/caja/abrir', {'cajero'}),
    ('post', '/caja/cerrar', {'cajero'}),
    ('post', '/caja/venta', {'cajero'}),
]
CORREOS = {'cliente': CLIENTE1, 'cajero': CAJERO_REAL, 'administrador': ADMIN}


@pytest.mark.parametrize('metodo,ruta,permitidos', RUTAS)
def test_anonimo_no_entra(client, metodo, ruta, permitidos):
    r = getattr(client, metodo)(ruta)
    assert r.status_code in (302, 401)
    if r.status_code == 302:
        assert '/iniciar-sesion' in r.headers['Location']


@pytest.mark.parametrize('metodo,ruta,permitidos', RUTAS)
@pytest.mark.parametrize('rol', ['cliente', 'cajero', 'administrador'])
def test_cada_rol_solo_entra_donde_le_corresponde(como, metodo, ruta, permitidos, rol):
    r = getattr(como(CORREOS[rol]), metodo)(ruta)
    if rol in permitidos:
        assert r.status_code != 403, f'{rol} debería poder usar {ruta}'
    else:
        assert r.status_code == 403, f'{rol} NO debería usar {ruta}'


def test_apis_de_reserva_rechazan_a_no_clientes(como):
    assert como(CAJERO_REAL).post('/api/reservas', json={}).status_code == 403
    assert como(ADMIN).post('/api/reservas', json={}).status_code == 403


def test_cajero_solo_ve_las_reservas_de_su_sede(app, como):
    """Una reserva de Mega Plaza no aparece ni se puede validar desde Real Plaza."""
    cliente = como(CLIENTE1)
    franja = franja_libre(unidad('Mega Plaza').id_flota)
    r = cliente.post('/api/reservas', json={'items': [{'id_franja': franja.id_franja}]})
    assert r.status_code == 201
    id_reserva = r.get_json()['id_reserva']
    assert cliente.post(f'/api/reservas/{id_reserva}/comprobante',
                        data={'comprobante': imagen()}).status_code == 201

    real, mega, admin = como(CAJERO_REAL), como(CAJERO_MEGA), como(ADMIN)
    assert real.get('/api/caja/reservas').get_json() == []
    assert len(mega.get('/api/caja/reservas').get_json()) == 1
    assert len(admin.get('/api/caja/reservas').get_json()) == 1

    assert real.post(f'/api/reservas/{id_reserva}/aceptar').status_code == 404
    assert real.post(f'/api/reservas/{id_reserva}/rechazar', json={'motivo': 'x'}).status_code == 404
    id_comprobante = cliente.get('/api/mis-reservas').get_json()[0]['comprobante']['id_comprobante']
    assert real.get(f'/comprobantes/{id_comprobante}').status_code == 404
    assert mega.get(f'/comprobantes/{id_comprobante}').status_code == 200


def test_un_cliente_no_ve_el_comprobante_de_otro(app, como):
    c1 = como(CLIENTE1)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = c1.post('/api/reservas', json={'items': [{'id_franja': franja.id_franja}]}).get_json()['id_reserva']
    c1.post(f'/api/reservas/{id_reserva}/comprobante', data={'comprobante': imagen()})
    id_comp = c1.get('/api/mis-reservas').get_json()[0]['comprobante']['id_comprobante']

    c2 = como('cliente2@ejemplo.pe')
    assert c2.get(f'/comprobantes/{id_comp}').status_code == 404
    assert c2.post(f'/api/reservas/{id_reserva}/cancelar').status_code == 404
    assert c1.get(f'/comprobantes/{id_comp}').status_code == 200


def test_cajero_solo_vende_unidades_de_su_sede(app, como):
    real = como(CAJERO_REAL)
    abrir_caja(real)
    otra = unidad('Mega Plaza')
    r = real.post('/caja/venta', data={'id_flota': otra.id_flota, 'bloques': 1, 'metodo_pago': 'efectivo'})
    assert r.status_code == 302                       # vuelve con un aviso, sin vender
    from app.models import Venta
    assert Venta.query.count() == 0
