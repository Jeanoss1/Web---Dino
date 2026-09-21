from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.database import db
from app.models.Flota import Flota
from app.models.Franja import Franja
from app.services import validadores as v
from app.services.errores import ErrorNegocio
from app.services.tarifas import tarifa_vigente


def _hora(texto):
    h, m = texto.split(':')
    return datetime.min.replace(hour=int(h), minute=int(m)).time()


def asegurar_franjas(dia):
    """Crea las franjas del día (bloques consecutivos de la tarifa) para cada
    unidad de flota activa que aún no las tenga."""
    cfg = current_app.config
    paso = timedelta(minutes=tarifa_vigente().minutos)
    apertura = datetime.combine(dia, _hora(cfg['HORA_APERTURA']))
    cierre = datetime.combine(dia, _hora(cfg['HORA_CIERRE']))

    con_franjas = {
        f for (f,) in db.session.query(Franja.id_flota).filter(Franja.fecha == dia).distinct()
    }
    nuevas = 0
    for unidad in Flota.query.filter(Flota.estado != 'inactivo').all():
        if unidad.id_flota in con_franjas:
            continue
        inicio = apertura
        while inicio + paso <= cierre:
            db.session.add(Franja(
                fecha=dia, horario_inicio=inicio, horario_fin=inicio + paso,
                estado='disponible', capacidad=1, id_flota=unidad.id_flota,
            ))
            inicio += paso
            nuevas += 1
    if nuevas:
        try:
            db.session.commit()
        except IntegrityError:      # otro proceso las creó al mismo tiempo
            db.session.rollback()
    return nuevas


def validar_fecha_reservable(dia):
    hoy = date.today()
    limite = hoy + timedelta(days=current_app.config['DIAS_ANTICIPACION'])
    if dia < hoy:
        raise ErrorNegocio('No puedes reservar en una fecha pasada.')
    if dia > limite:
        raise ErrorNegocio(f'Solo puedes reservar hasta {current_app.config["DIAS_ANTICIPACION"]} días adelante.')


def listar_disponibles(id_flota, fecha_texto):
    """Franjas libres de una unidad en un día (solo las que aún no empezaron)."""
    from app.services.reservas import expirar_pendientes

    dia = v.fecha(fecha_texto) if fecha_texto else date.today()
    validar_fecha_reservable(dia)
    id_flota = v.entero(id_flota, 'id_flota', 1, 10**9)
    unidad = db.session.get(Flota, id_flota)
    if unidad is None or unidad.estado != 'disponible':
        return []
    expirar_pendientes()
    asegurar_franjas(dia)
    return (
        Franja.query
        .filter(Franja.id_flota == id_flota, Franja.fecha == dia,
                Franja.estado == 'disponible', Franja.horario_inicio >= datetime.now())
        .order_by(Franja.horario_inicio).all()
    )
