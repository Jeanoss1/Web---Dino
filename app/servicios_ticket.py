"""Tickets de acceso de las reservas en línea.

- HU03 (CA03.3): al aceptar el pago de una reserva se emite un ticket con
  código único vinculado a ella.
- HU05 (CA05.4 y CA05.5): en caja se valida el ticket por su código y, al
  asignar las unidades, queda marcado como usado y no sirve otra vez.

El ticket es un comprobante interno de acceso; el comprobante de pago
tributario (boleta) es un documento aparte.
"""
import uuid

from app.database import db
from app.models.Ticket import Ticket
from app.tiempo import ahora


def _codigo_nuevo():
    """Mismo formato que los tickets de venta: T<AAMMDD>-XXXXXX, sin repetir."""
    while True:
        codigo = f"T{ahora():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        if not Ticket.query.filter_by(codigo=codigo).first():
            return codigo


def emitir_ticket_reserva(reserva):
    """Crea el ticket de la reserva si aún no tiene uno. No hace commit."""
    if reserva.ticket is not None:
        return reserva.ticket
    ticket = Ticket(codigo=_codigo_nuevo(), reserva=reserva, estado='emitido')
    db.session.add(ticket)
    return ticket


def ticket_a_dict(ticket):
    reserva = ticket.reserva
    datos = {
        'codigo': ticket.codigo,
        'estado': ticket.estado,
        'fecha_emision': ticket.fecha_emision.isoformat() if ticket.fecha_emision else None,
        'emitido': ticket.fecha_emision.strftime('%d-%m-%Y %H:%M') if ticket.fecha_emision else '',
        'fecha_uso': ticket.fecha_uso.isoformat() if ticket.fecha_uso else None,
        'url': f'/tickets/{ticket.codigo}',
    }
    if reserva is not None:
        datos.update({
            'id_reserva': reserva.id_reserva,
            'cliente': f'{reserva.cliente.nombre} {reserva.cliente.apellido}',
            'dni': reserva.cliente.dni,
            'total': float(reserva.total or 0),
            'unidades': [
                {
                    'id_flota': d.id_flota,
                    'unidad': d.flota.nombre,
                    'estado_unidad': d.flota.estado,
                    'sede': d.flota.sucursal.nombre,
                    'fecha': d.turno.fecha.strftime('%d-%m-%Y'),
                    'inicio': d.turno.horario_inicio.strftime('%H:%M'),
                    'fin': d.turno.horario_fin.strftime('%H:%M'),
                }
                for d in reserva.detalles
            ],
        })
    return datos


def validar_ticket(codigo, id_sucursal_cajero=None):
    """Devuelve (ticket, error, http). Comprueba que exista, que no esté usado,
    que su reserva esté confirmada y, si el cajero tiene sede, que las
    unidades sean de esa sede."""
    codigo = (codigo or '').strip().upper()
    if not codigo:
        return None, 'Ingresa el código del ticket', 400
    ticket = Ticket.query.filter_by(codigo=codigo).first()
    if ticket is None or ticket.reserva is None:
        return None, 'El ticket no existe', 404
    if ticket.estado == 'usado':
        hora = ticket.fecha_uso.strftime('%d-%m-%Y %H:%M') if ticket.fecha_uso else ''
        return ticket, f'El ticket ya fue utilizado {hora}'.strip(), 409
    if ticket.reserva.estado != 'confirmada':
        return ticket, 'La reserva del ticket no está confirmada', 409
    if id_sucursal_cajero and any(
            d.flota.id_sucursal != id_sucursal_cajero for d in ticket.reserva.detalles):
        return ticket, 'El ticket corresponde a otra sede', 403
    return ticket, None, 200


def usar_ticket(ticket, id_validador):
    """Asigna las unidades al cliente y marca el ticket como usado. Devuelve un
    mensaje de error (sin cambiar nada) si alguna unidad no está disponible."""
    for d in ticket.reserva.detalles:
        if d.flota.estado == 'mantenimiento':
            return f'{d.flota.nombre} está en mantenimiento'
        if d.flota.estado != 'disponible':
            return f'{d.flota.nombre} está en uso'
    ticket.estado = 'usado'
    ticket.fecha_uso = ahora()
    ticket.id_validador = id_validador
    db.session.commit()
    return None
