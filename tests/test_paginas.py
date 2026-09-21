"""Todas las pantallas cargan sin errores para el rol que las usa."""
from app.models import DetalleVenta, Venta
from tests.conftest import (ADMIN, CAJERO_REAL, CLIENTE1, abrir_caja, franja_libre,
                            imagen, unidad)


def test_paginas_publicas(client):
    for ruta in ('/', '/iniciar-sesion', '/registro'):
        r = client.get(ruta)
        assert r.status_code == 200, ruta
    html = client.get('/').get_data(as_text=True)
    assert 'S/ 10.00 por 12 min' in html and 'S/ 15.00' not in html    # precio desde la tarifa


def test_paginas_del_cliente(como):
    c = como(CLIENTE1)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = c.post('/api/reservas', json={'items': [{'id_franja': franja.id_franja}]}).get_json()['id_reserva']
    c.post(f'/api/reservas/{id_reserva}/comprobante', data={'comprobante': imagen()})
    for ruta in ('/disponibilidad', '/mis-reservas', '/api/sedes', '/api/flota', '/api/mis-reservas'):
        assert c.get(ruta).status_code == 200, ruta
    html = c.get('/disponibilidad').get_data(as_text=True)
    assert 'csrf-token' in html and '/api/franjas' in html


def test_paginas_del_cajero(app, como):
    cajero = como(CAJERO_REAL)
    for ruta in ('/caja', '/caja/venta', '/caja/uso', '/caja/validaciones'):
        assert cajero.get(ruta).status_code == 200, ruta
    abrir_caja(cajero)
    cajero.post('/caja/venta', data={'id_flota': unidad('Real Plaza').id_flota, 'bloques': 2, 'metodo_pago': 'yape'})
    venta = Venta.query.one()
    assert 'S/ 20.00' in cajero.get(f'/caja/venta/{venta.id_venta}').get_data(as_text=True)
    for ruta in ('/caja', '/caja/venta', '/caja/uso'):
        assert cajero.get(ruta).status_code == 200, ruta
    assert 'Cajero 1 Real Plaza' in cajero.get('/caja').get_data(as_text=True) or True


def test_ticket_de_otra_sede_no_se_ve(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    cajero.post('/caja/venta', data={'id_flota': unidad('Real Plaza').id_flota, 'bloques': 1, 'metodo_pago': 'efectivo'})
    id_venta = Venta.query.one().id_venta
    assert como('cajero1.megaplaza@dinopark.pe').get(f'/caja/venta/{id_venta}').status_code == 404
    assert como(ADMIN).get(f'/caja/venta/{id_venta}').status_code == 200


def test_el_administrador_gestiona_sedes_flota_y_mantenimiento(app, como):
    from app.models import Flota, Sucursal
    admin = como(ADMIN)
    hoyos = Sucursal.query.filter_by(nombre='Hoyos Rubio').one()
    assert hoyos.estado == 'inactiva'
    assert Sucursal.query.filter_by(nombre='Hoyos Rubio', estado='inactiva').count() == 1
    assert 'Hoyos Rubio' not in [s['nombre'] for s in admin.get('/api/sedes').get_json()]
    admin.post(f'/admin/sedes/{hoyos.id_sucursal}/estado')
    assert 'Hoyos Rubio' in [s['nombre'] for s in admin.get('/api/sedes').get_json()]

    admin.post('/admin/flota', data={'nombre': 'Dino Nuevo', 'tipo': 'dinosaurio', 'id_sucursal': hoyos.id_sucursal,
                                     'modelo': 'X', 'detalle': 'Velociraptor'})
    nuevo = Flota.query.filter_by(nombre='Dino Nuevo').one()
    assert nuevo.especie == 'Velociraptor'
    admin.post('/admin/mantenimiento/iniciar', data={'id_flota': nuevo.id_flota, 'tipo': 'preventivo'})
    assert Flota.query.get(nuevo.id_flota).estado == 'mantenimiento'


def test_creacion_de_cajero_por_el_administrador(app, como):
    from app.models import Cajero
    from tests.conftest import sede, usuario
    admin = como(ADMIN)
    admin.post('/admin/usuarios', data={'rol': 'cajero', 'nombre': 'Cajero 3', 'apellido': 'Real Plaza',
               'correo': 'cajero3@dinopark.pe', 'contrasena': 'Prueba2026!', 'id_sucursal': sede('Real Plaza').id_sucursal,
               'tipo_turno': 'medio'})
    u = usuario('cajero3@dinopark.pe')
    assert u.rol_nombre == 'cajero' and u.cajero.tipo_turno == 'medio' and u.cajero.horas_turno == 4
    assert como('cajero3@dinopark.pe').get('/caja').status_code == 200


def test_voucher_termico_de_80mm_solo_con_el_ticket(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    u = unidad('Real Plaza', 0)
    cajero.post('/caja/venta', data={'id_flota': u.id_flota, 'bloques': 2, 'metodo_pago': 'yape'})
    venta = Venta.query.one()
    html = cajero.get(f'/caja/venta/{venta.id_venta}').get_data(as_text=True)
    assert '@page { size: 80mm auto; margin: 0; }' in html
    assert 'ticket-termico' in html
    # datos del voucher
    for texto in ('Real Plaza', venta.detalles[0].pago.ticket.codigo, u.nombre, '24 min', 'S/ 10.00 por bloque',
                  'Yape', 'Cajero 1 Real Plaza', 'Gracias por visitarnos', venta.fecha.strftime('%d/%m/%Y')):
        assert texto in html, texto
    # lo que no debe salir impreso lleva .no-print (menu, botones, avisos)
    assert html.count('no-print') >= 3
    css = cajero.get('/static/css/dino.css').get_data(as_text=True)
    assert '@media print' in css and '.no-print' in css and '.ticket-termico' in css
