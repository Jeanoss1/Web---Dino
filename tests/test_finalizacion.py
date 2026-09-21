"""Finalización automática de los alquileres."""
import time
from datetime import datetime, timedelta

from app.database import db
from app.models import DetalleVenta, Flota, RegistroUso, Reserva
from app.scheduler import iniciar_planificador
from app.services import uso as servicio_uso
from tests.conftest import (CAJERO_REAL, CLIENTE1, abrir_caja, franja_libre, imagen,
                            unidad, vencer_todo)


def vender(cajero, u, bloques=1):
    return cajero.post('/caja/venta', data={'id_flota': u.id_flota, 'bloques': bloques, 'metodo_pago': 'efectivo'})


def test_la_venta_guarda_inicio_y_fin_previsto(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    vender(cajero, unidad('Real Plaza'), 3)
    u = RegistroUso.query.one()
    assert u.estado == 'en_curso' and u.minutos_previstos == 36
    assert u.hora_fin_prevista - u.hora_inicio == timedelta(minutes=36)


def test_finaliza_solo_al_vencer_y_libera_la_unidad(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    unidad_real = unidad('Real Plaza')
    vender(cajero, unidad_real)
    assert servicio_uso.finalizar_vencidos() == 0                    # aún no vence
    assert vender(cajero, unidad_real).status_code == 302
    assert RegistroUso.query.count() == 1                            # unidad ocupada: no se vende otra vez

    assert vencer_todo() == 1                                        # ya venció
    db.session.expire_all()
    u = RegistroUso.query.one()
    assert (u.estado, u.minutos_usados, u.finalizado_por) == ('finalizado', 12, 'automatico')
    assert u.hora_fin == u.hora_fin_prevista
    vender(cajero, unidad_real)                                      # la unidad quedó libre
    assert RegistroUso.query.count() == 2


def test_no_se_procesa_dos_veces_el_mismo_alquiler(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    unidad_real = unidad('Real Plaza')
    vender(cajero, unidad_real)
    id_uso = RegistroUso.query.one().id_uso
    fin = datetime.now() + timedelta(hours=1)

    assert servicio_uso._cerrar(id_uso, fin, 12, 'automatico') is True
    assert servicio_uso._cerrar(id_uso, fin, 12, 'automatico') is False   # segundo proceso: no hace nada
    assert vencer_todo() == 0
    db.session.expire_all()
    assert db.session.get(Flota, unidad_real.id_flota).ciclos_uso == 1    # se sumó una sola vez


def test_finalizacion_perezosa_al_consultar_sin_scheduler(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    vender(cajero, unidad('Real Plaza'))
    u = RegistroUso.query.one()
    u.hora_inicio -= timedelta(minutes=30)
    u.hora_fin_prevista -= timedelta(minutes=30)                      # ya pasó su hora
    db.session.commit()

    assert cajero.get('/caja/uso').status_code == 200                # basta con mirar la pantalla
    db.session.expire_all()
    assert RegistroUso.query.one().estado == 'finalizado'


def test_el_proceso_en_segundo_plano_finaliza(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    vender(cajero, unidad('Real Plaza'))
    u = RegistroUso.query.one()
    u.hora_fin_prevista = datetime.now() - timedelta(seconds=1)
    db.session.commit()

    planificador = iniciar_planificador(app, segundos=3600)          # el primer ciclo corre de inmediato
    try:
        for _ in range(50):
            time.sleep(0.1)
            db.session.expire_all()
            if RegistroUso.query.one().estado == 'finalizado':
                break
        assert RegistroUso.query.one().estado == 'finalizado'
    finally:
        planificador.shutdown(wait=False)


def test_reserva_confirmada_se_completa_al_terminar_el_tiempo(app, como):
    cliente, cajero = como(CLIENTE1), como(CAJERO_REAL)
    franja = franja_libre(unidad('Real Plaza').id_flota)
    id_reserva = cliente.post('/api/reservas', json={'items': [{'id_franja': franja.id_franja}]}).get_json()['id_reserva']
    cliente.post(f'/api/reservas/{id_reserva}/comprobante', data={'comprobante': imagen()})
    cajero.post(f'/api/reservas/{id_reserva}/aceptar')

    detalle = DetalleVenta.query.one()
    cajero.post('/caja/uso/iniciar', data={'id_detalle': detalle.id_detalle_venta})   # llega el cliente
    assert RegistroUso.query.one().estado == 'en_curso'
    vencer_todo()
    db.session.expire_all()
    assert db.session.get(Reserva, id_reserva).estado == 'completada'
