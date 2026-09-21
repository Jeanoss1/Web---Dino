import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.database import db
from app.models.DetalleReserva import DetalleReserva
from app.models.DetalleVenta import DetalleVenta
from app.models.Flota import Flota
from app.models.Franja import Franja
from app.models.MovimientoCaja import MovimientoCaja
from app.models.Pago import Pago
from app.models.RegistroUso import RegistroUso
from app.models.Ticket import Ticket
from app.models.Venta import Venta
from app.services import cajas, franjas, uso
from app.services import validadores as v
from app.services.errores import ErrorNegocio
from app.services.tarifas import calcular, tarifa_vigente

METODOS_PAGO = ('efectivo', 'yape')


def _emitir_pago(detalle, metodo):
    """Cada detalle genera su pago y su ticket."""
    pago = Pago(monto=detalle.subtotal, metodo_pago=metodo, estado='pagado')
    pago.detalle_venta = detalle
    pago.ticket = Ticket(
        codigo=f'T{datetime.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}'
    )
    db.session.add(pago)
    db.session.flush()
    return pago


def crear_venta_presencial(usuario, cajero, id_flota, bloques, metodo):
    """Alquiler en el local: precio siempre desde la tabla de tarifas."""
    if cajero is None or cajero.estado != 'activo':
        raise ErrorNegocio('Solo un cajero activo puede registrar ventas.', 403)
    caja = cajas.caja_abierta(usuario.id_usuario)
    if caja is None:
        raise ErrorNegocio('Abre tu caja antes de registrar ventas.')
    if metodo not in METODOS_PAGO:
        raise ErrorNegocio('El método de pago debe ser efectivo o Yape.')

    uso.finalizar_vencidos(cajero.id_sucursal)       # libera las unidades cuyo tiempo ya venció
    unidad = db.session.get(Flota, v.entero(id_flota, 'unidad', 1, 10**9))
    if unidad is None or unidad.id_sucursal != cajero.id_sucursal:
        raise ErrorNegocio('La unidad no pertenece a tu sede.', 404)
    if unidad.estado != 'disponible':
        raise ErrorNegocio('La unidad no está disponible (mantenimiento o inactiva).')
    if RegistroUso.query.filter_by(id_flota=unidad.id_flota, estado='en_curso').first():
        raise ErrorNegocio('La unidad está en uso en este momento.')

    tarifa = tarifa_vigente()
    calculo = calcular(bloques, tarifa)
    ahora = datetime.now()
    fin = ahora + timedelta(minutes=calculo['minutos'])

    # No vender un horario que ya tiene una reserva de un cliente
    choque = (
        DetalleReserva.query.join(Franja, Franja.id_franja == DetalleReserva.id_franja)
        .filter(DetalleReserva.id_flota == unidad.id_flota, DetalleReserva.activo.is_(True),
                Franja.horario_inicio < fin, Franja.horario_fin > ahora)
        .first()
    )
    if choque:
        raise ErrorNegocio('La unidad tiene una reserva de un cliente en ese horario.')

    venta = Venta(
        fecha=ahora, tipo_pago=metodo, estado='pagada', origen='presencial',
        id_usuario=usuario.id_usuario, id_sucursal=cajero.id_sucursal,
    )
    detalle = DetalleVenta(
        id_flota=unidad.id_flota, precio=calculo['precio_bloque'],
        cantidad=calculo['bloques'], minutos=calculo['minutos'], fecha_servicio=ahora.date(),
    )
    detalle.calcular_subtotal()
    venta.detalles.append(detalle)
    venta.total = detalle.subtotal
    db.session.add(venta)
    db.session.flush()

    pago = _emitir_pago(detalle, metodo)
    uso.comenzar(usuario, detalle, calculo['minutos'], ahora)     # el tiempo corre desde la venta
    if metodo == 'efectivo':
        db.session.add(MovimientoCaja(
            tipo='ingreso', monto=detalle.subtotal, origen='venta', ticket=pago.ticket,
            descripcion=f'Venta #{venta.id_venta}', id_caja=caja.id_caja,
        ))

    # Las franjas de ese rato ya no se pueden reservar por internet
    franjas.asegurar_franjas(ahora.date())
    (Franja.query
     .filter(Franja.id_flota == unidad.id_flota, Franja.estado == 'disponible',
             Franja.horario_inicio < fin, Franja.horario_fin > ahora)
     .update({'estado': 'ocupada'}, synchronize_session=False))
    db.session.commit()
    return venta


def registrar_venta_reserva(reserva, validador):
    """Al aceptar el pago Yape de una reserva se registra la venta a nombre
    del cajero que validó (sin hacer commit: lo hace quien la llama)."""
    if not reserva.detalles:
        raise ErrorNegocio('La reserva no tiene detalles.')
    activos = [d for d in reserva.detalles if d.activo]
    unitario = (reserva.total / len(activos)).quantize(Decimal('0.01'))
    venta = Venta(
        fecha=datetime.now(), tipo_pago='yape', estado='pagada', origen='reserva',
        id_usuario=validador.id_usuario, id_sucursal=reserva.id_sucursal,
        id_reserva=reserva.id_reserva,
    )
    for d in activos:
        minutos = int((d.franja.horario_fin - d.franja.horario_inicio).total_seconds() // 60)
        detalle = DetalleVenta(
            id_flota=d.id_flota, precio=unitario, cantidad=1, minutos=minutos,
            fecha_servicio=d.franja.fecha, id_detalle_reserva=d.id_detalle,
        )
        detalle.calcular_subtotal()
        venta.detalles.append(detalle)
    venta.total = sum((x.subtotal for x in venta.detalles), Decimal('0'))
    db.session.add(venta)
    db.session.flush()
    for detalle in venta.detalles:
        _emitir_pago(detalle, 'yape')
    return venta


def ventas_del_dia(usuario_id, dia=None):
    dia = dia or date.today()
    inicio = datetime.combine(dia, datetime.min.time())
    return (
        Venta.query.filter(Venta.id_usuario == usuario_id, Venta.fecha >= inicio,
                           Venta.fecha < inicio + timedelta(days=1))
        .order_by(Venta.fecha.desc()).all()
    )
