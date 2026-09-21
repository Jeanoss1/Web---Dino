"""Proceso en segundo plano que finaliza solos los alquileres vencidos (cada 30 s),
aunque nadie tenga el navegador abierto."""
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import db
from app.services import uso

INTERVALO_SEGUNDOS = 30


def iniciar_planificador(app, segundos=INTERVALO_SEGUNDOS):
    def tarea():
        with app.app_context():
            try:
                finalizados = uso.finalizar_vencidos()
                if finalizados:
                    app.logger.info('Alquileres finalizados automáticamente: %s', finalizados)
            except Exception:                       # un fallo no debe matar el proceso
                app.logger.exception('Error al finalizar alquileres vencidos')
                db.session.rollback()
            finally:
                db.session.remove()

    planificador = BackgroundScheduler(daemon=True)
    planificador.add_job(
        tarea, 'interval', seconds=segundos, id='finalizar_vencidos',
        max_instances=1, coalesce=True, next_run_time=datetime.now(),
    )
    planificador.start()
    return planificador
