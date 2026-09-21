"""Control del tiempo de uso de cada alquiler.

Cada alquiler guarda su hora de inicio y su hora de fin prevista (bloques x 12 min)
y se FINALIZA SOLO al vencer:
  * un proceso en segundo plano (app/scheduler.py) lo revisa cada 30 segundos, y
  * además se finaliza "de forma perezosa" cada vez que alguien consulta alquileres.
Finalizar es idempotente: un UPDATE condicionado (`WHERE estado = 'en_curso'`) garantiza
que un mismo alquiler se procese una sola vez aunque haya varios procesos a la vez.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import update

from app.database import db
from app.models.DetalleVenta import DetalleVenta
from app.models.RegistroUso import RegistroUso
from app.models.Venta import Venta
from app.services import validadores as v
from app.services.errores import ErrorNegocio


def detalles_del_dia(id_sucursal, dia=None):
    """Alquileres vendidos para hoy en la sede (presenciales y reservas confirmadas)."""
    finalizar_vencidos(id_sucursal)
    dia = dia or date.today()
    return (
        DetalleVenta.query.join(Venta, Venta.id_venta == DetalleVenta.id_venta)
        .filter(Venta.id_sucursal == id_sucursal, Venta.estado == 'pagada',
                DetalleVenta.fecha_servicio == dia)
        .order_by(DetalleVenta.id_detalle_venta).all()
    )


def _detalle_de_mi_sede(cajero, id_detalle):
    detalle = db.session.get(DetalleVenta, v.entero(id_detalle, 'alquiler', 1, 10**9))
    if detalle is None or detalle.venta.id_sucursal != cajero.id_sucursal:
        raise ErrorNegocio('Alquiler no encontrado.', 404)
    return detalle


# ------------------------------------------------------------------- inicio
def comenzar(usuario, detalle, minutos_previstos, ahora=None):
    """Registra el inicio del alquiler y su hora de fin prevista (sin hacer commit)."""
    ahora = ahora or datetime.now()
    uso = RegistroUso(
        id_detalle_venta=detalle.id_detalle_venta, id_flota=detalle.id_flota,
        id_sucursal=detalle.venta.id_sucursal, id_usuario=usuario.id_usuario,
        hora_inicio=ahora, minutos_previstos=minutos_previstos,
        hora_fin_prevista=ahora + timedelta(minutes=minutos_previstos), estado='en_curso',
    )
    db.session.add(uso)
    db.session.flush()
    _sumar_contador(uso, 'encendidos', 1, ahora)         # carros y motos: +1 al encender
    return uso


def _sumar_contador(uso, cuando, cantidad, fecha):
    """Suma `cantidad` al contador del sistema de la unidad si su contador es del tipo `cuando`.
    Es un UPDATE atómico (col = col + n), seguro con procesos concurrentes."""
    from app.models.Flota import Flota
    resultado = db.session.execute(
        update(Flota).where(Flota.id_flota == uso.id_flota, Flota.tipo_contador == cuando)
        .values(contador_sistema=Flota.contador_sistema + cantidad),
        execution_options={'synchronize_session': False},
    )
    if resultado.rowcount == 1:
        uso.contador_delta = cantidad
        uso.contador_fecha = fecha
        db.session.flush()


def iniciar(usuario, cajero, id_detalle):
    """Inicia el tiempo de un alquiler ya vendido (p. ej. una reserva confirmada cuando llega el cliente)."""
    finalizar_vencidos(cajero.id_sucursal)
    detalle = _detalle_de_mi_sede(cajero, id_detalle)
    if detalle.uso_en_curso:
        raise ErrorNegocio('Este alquiler ya está en curso.')
    restante = detalle.minutos - detalle.minutos_usados
    if restante <= 0:
        raise ErrorNegocio('Ya se usó todo el tiempo vendido de este alquiler.')
    if RegistroUso.query.filter_by(id_flota=detalle.id_flota, estado='en_curso').first():
        raise ErrorNegocio('Esa unidad ya está en uso.')
    uso = comenzar(usuario, detalle, restante)
    db.session.commit()
    return uso


# --------------------------------------------------------------- finalización
def _cerrar(id_uso, hora_fin, minutos, por, motivo=None):
    """Finaliza un uso UNA sola vez. Devuelve False si otro proceso ya lo finalizó."""
    resultado = db.session.execute(
        update(RegistroUso)
        .where(RegistroUso.id_uso == id_uso, RegistroUso.estado == 'en_curso')
        .values(estado='finalizado', hora_fin=hora_fin, minutos_usados=minutos,
                finalizado_por=por, motivo_fin=motivo),
        execution_options={'synchronize_session': False},
    )
    if resultado.rowcount != 1:
        return False                      # otro proceso ya lo finalizó: no se vuelve a procesar
    uso = db.session.get(RegistroUso, id_uso)
    db.session.refresh(uso)
    _al_finalizar(uso)
    db.session.commit()
    return True


def _al_finalizar(uso):
    """Efectos de terminar un uso: contador de minutos, ciclos de la unidad y reserva completada."""
    from app.models.Flota import Flota
    _sumar_contador(uso, 'minutos', uso.minutos_usados or 0, uso.hora_fin)   # dinosaurios: + minutos
    db.session.execute(
        update(Flota).where(Flota.id_flota == uso.id_flota)
        .values(ciclos_uso=Flota.ciclos_uso + 1),
        execution_options={'synchronize_session': False},
    )
    reserva = uso.detalle_venta.venta.reserva
    if reserva is not None and reserva.estado == 'confirmada':
        db.session.flush()
        if all(any(u.estado == 'finalizado' for u in d.usos) for d in reserva.venta.detalles):
            reserva.estado = 'completada'


def finalizar_vencidos(id_sucursal=None, ahora=None):
    """Finaliza todos los alquileres cuya hora de fin prevista ya pasó. Devuelve cuántos."""
    ahora = ahora or datetime.now()
    consulta = db.session.query(RegistroUso.id_uso, RegistroUso.hora_fin_prevista,
                                RegistroUso.minutos_previstos).filter(
        RegistroUso.estado == 'en_curso', RegistroUso.hora_fin_prevista <= ahora)
    if id_sucursal:
        consulta = consulta.filter(RegistroUso.id_sucursal == id_sucursal)
    total = 0
    for id_uso, fin_previsto, previstos in consulta.all():
        if _cerrar(id_uso, fin_previsto, previstos, 'automatico'):
            total += 1
    return total


def finalizar_antes(cajero, id_uso, motivo):
    """Caso excepcional: el cajero termina el alquiler antes de tiempo, con motivo.
    Se cuentan los minutos realmente transcurridos."""
    finalizar_vencidos(cajero.id_sucursal)
    uso = db.session.get(RegistroUso, v.entero(id_uso, 'uso', 1, 10**9))
    if uso is None or uso.id_sucursal != cajero.id_sucursal:
        raise ErrorNegocio('Registro de uso no encontrado.', 404)
    if uso.estado != 'en_curso':
        raise ErrorNegocio('Este alquiler ya fue finalizado.')
    motivo = v.texto(motivo, 'motivo', 3, 200)
    ahora = datetime.now()
    minutos = max(1, min(uso.minutos_previstos, round((ahora - uso.hora_inicio).total_seconds() / 60)))
    if not _cerrar(uso.id_uso, ahora, minutos, 'cajero', motivo):
        raise ErrorNegocio('Este alquiler ya fue finalizado.')
    return db.session.get(RegistroUso, id_uso)
