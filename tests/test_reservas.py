from datetime import datetime, timedelta

from app.database import db
from app.models import ComprobanteReserva, DetalleReserva, Franja, Reserva, Venta
from tests.conftest import (CAJERO_REAL, CLIENTE1, CLIENTE2, franja_libre, imagen,
                            unidad, usuario)


def reservar(cliente, franja):
    return cliente.post('/api/reservas', json={'items': [{'id_franja': franja.id_franja}]})


def test_flujo_completo_reserva_pago_yape_y_validacion(app, como):
    cliente, cajero = como(CLIENTE1), como(CAJERO_REAL)
    franja = franja_libre(unidad('Real Plaza').id_flota)

    r = reservar(cliente, franja)
    assert r.status_code == 201
    reserva = r.get_json()
    assert reserva['estado'] == 'pendiente_pago' and reserva['total'] == 10.0

    r = cliente.post(f'/api/reservas/{reserva["id_reserva"]}/comprobante', data={'comprobante': imagen()})
    assert r.status_code == 201 and r.get_json()['estado'] == 'pago_en_revision'

    pendientes = cajero.get('/api/caja/reservas').get_json()
    assert [p['id_reserva'] for p in pendientes] == [reserva['id_reserva']]

    r = cajero.post(f'/api/reservas/{reserva["id_reserva"]}/aceptar')
    assert r.status_code == 200 and r.get_json()['estado'] == 'confirmada'
    comp = r.get_json()['comprobante']
    assert comp['validado_por'] == 'Cajero 1 Real Plaza' and comp['fecha_validacion']

    venta = Venta.query.one()                        # la reserva confirmada genera su venta
    assert (venta.origen, venta.tipo_pago, venta.total) == ('reserva', 'yape', 10)
    assert venta.id_usuario == usuario(CAJERO_REAL).id_usuario and venta.minutos == 12


def test_rechazo_exige_motivo_y_libera_el_horario(app, como):
    cliente, cajero = como(CLIENTE1), como(CAJERO_REAL)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = reservar(cliente, franja).get_json()['id_reserva']
    cliente.post(f'/api/reservas/{id_reserva}/comprobante', data={'comprobante': imagen()})

    assert cajero.post(f'/api/reservas/{id_reserva}/rechazar', json={}).status_code == 400
    r = cajero.post(f'/api/reservas/{id_reserva}/rechazar', json={'motivo': 'El monto no coincide'})
    assert r.status_code == 200 and r.get_json()['estado'] == 'rechazada'
    assert r.get_json()['comprobante']['motivo_rechazo'] == 'El monto no coincide'
    assert Venta.query.count() == 0

    db.session.expire_all()
    assert db.session.get(Franja, franja.id_franja).estado == 'disponible'
    assert reservar(como(CLIENTE2), franja).status_code == 201     # otro cliente ya puede tomarla


def test_no_se_puede_reservar_dos_veces_la_misma_franja(app, como):
    franja = franja_libre(unidad('Real Plaza').id_flota)
    assert reservar(como(CLIENTE1), franja).status_code == 201
    r = reservar(como(CLIENTE2), franja)
    assert r.status_code == 400
    assert DetalleReserva.query.filter_by(id_franja=franja.id_franja, activo=True).count() == 1


def test_la_base_de_datos_impide_dos_detalles_activos_en_una_franja(app):
    """Respaldo a nivel de BD contra la doble reserva (aunque falle la lógica)."""
    import pytest
    from sqlalchemy.exc import IntegrityError
    franja = franja_libre(unidad('Real Plaza').id_flota)
    u = unidad('Real Plaza')
    for i in (1, 2):
        db.session.add(Reserva(id_cliente=1, id_sucursal=u.id_sucursal, estado='pendiente_pago'))
    db.session.flush()
    db.session.add(DetalleReserva(id_reserva=1, id_flota=u.id_flota, id_franja=franja.id_franja))
    db.session.flush()
    db.session.add(DetalleReserva(id_reserva=2, id_flota=u.id_flota, id_franja=franja.id_franja))
    with pytest.raises(IntegrityError):
        db.session.flush()
    db.session.rollback()


def test_el_cliente_puede_cancelar_y_libera_el_horario(app, como):
    cliente = como(CLIENTE1)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = reservar(cliente, franja).get_json()['id_reserva']
    r = cliente.post(f'/api/reservas/{id_reserva}/cancelar')
    assert r.status_code == 200 and r.get_json()['estado'] == 'cancelada'
    assert reservar(como(CLIENTE2), franja).status_code == 201


def test_reserva_vence_si_no_se_paga_a_tiempo(app, como):
    cliente = como(CLIENTE1)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = reservar(cliente, franja).get_json()['id_reserva']
    db.session.get(Reserva, id_reserva).vence_en = datetime.now() - timedelta(minutes=1)
    db.session.commit()
    estados = {r['id_reserva']: r['estado'] for r in cliente.get('/api/mis-reservas').get_json()}
    assert estados[id_reserva] == 'cancelada'
    assert reservar(como(CLIENTE2), franja).status_code == 201


def test_captura_valida_tipo_real_y_tamano(app, como):
    cliente = como(CLIENTE1)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = reservar(cliente, franja).get_json()['id_reserva']
    url = f'/api/reservas/{id_reserva}/comprobante'

    r = cliente.post(url, data={'comprobante': imagen('virus.png', b'MZ este no es una imagen')})
    assert r.status_code == 400                       # se mira el contenido, no la extensión
    r = cliente.post(url, data={'comprobante': imagen('grande.png', b'\x89PNG\r\n\x1a\n' + b'0' * (6 * 1024 * 1024))})
    assert r.status_code == 413
    assert cliente.post(url).status_code == 400       # sin archivo
    assert ComprobanteReserva.query.count() == 0


def test_el_nombre_del_archivo_lo_genera_el_servidor(app, como):
    import os
    cliente = como(CLIENTE1)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = reservar(cliente, franja).get_json()['id_reserva']
    cliente.post(f'/api/reservas/{id_reserva}/comprobante', data={'comprobante': imagen('../../evil.png')})
    guardado = ComprobanteReserva.query.one().archivo
    assert guardado.startswith(f'reserva{id_reserva}_') and guardado.endswith('.png')
    assert '..' not in guardado and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], guardado))


def test_la_misma_captura_no_sirve_para_dos_reservas(app, como):
    f1 = franja_libre(unidad('Real Plaza').id_flota, 0)
    f2 = franja_libre(unidad('Real Plaza').id_flota, 1)
    c1, c2 = como(CLIENTE1), como(CLIENTE2)
    r1 = reservar(c1, f1).get_json()['id_reserva']
    r2 = reservar(c2, f2).get_json()['id_reserva']
    assert c1.post(f'/api/reservas/{r1}/comprobante', data={'comprobante': imagen()}).status_code == 201
    assert c2.post(f'/api/reservas/{r2}/comprobante', data={'comprobante': imagen()}).status_code == 400


def test_no_reserva_en_el_pasado_ni_unidad_en_mantenimiento(app, como):
    cliente = como(CLIENTE1)
    u = unidad('Real Plaza')
    franja = franja_libre(u.id_flota)
    ayer = (datetime.now() - timedelta(days=1)).date().isoformat()
    assert cliente.get(f'/api/franjas?id_flota={u.id_flota}&fecha={ayer}').status_code == 400

    u.estado = 'mantenimiento'
    db.session.commit()
    assert reservar(cliente, franja).status_code == 400
    assert cliente.get(f'/api/franjas?id_flota={u.id_flota}&fecha={franja.fecha}').get_json() == []


def test_reservas_de_dos_sedes_no_se_mezclan(app, como):
    f_real = franja_libre(unidad('Real Plaza').id_flota)
    f_mega = franja_libre(unidad('Mega Plaza').id_flota)
    r = como(CLIENTE1).post('/api/reservas', json={'items': [{'id_franja': f_real.id_franja},
                                                             {'id_franja': f_mega.id_franja}]})
    assert r.status_code == 400
