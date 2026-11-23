"""Modelos de datos de Dino Park."""

from app.models.AsignacionTurno import AsignacionTurno
from app.models.Caja import Caja
from app.models.CapturaComprobante import CapturaComprobante
from app.models.Cliente import Cliente
from app.models.ComprobanteBase import ComprobanteBase
from app.models.ComprobanteReserva import ComprobanteReserva
from app.models.ComprobanteReservaEntrada import ComprobanteReservaEntrada
from app.models.DetalleReserva import DetalleReserva
from app.models.DetalleReservaEntrada import DetalleReservaEntrada
from app.models.DetalleVenta import DetalleVenta
from app.models.Flota import Carro, Dinosaurio, Flota, Moto
from app.models.LecturaFlota import LecturaFlota
from app.models.Mantenimiento import Mantenimiento
from app.models.MovimientoCaja import MovimientoCaja
from app.models.Pago import Pago
from app.models.PaqueteTarifa import PaqueteTarifa
from app.models.Repuesto import Repuesto
from app.models.Reserva import Reserva
from app.models.ReservaEntrada import ReservaEntrada
from app.models.Rol import Rol
from app.models.Sucursal import Sucursal
from app.models.Ticket import Ticket
from app.models.Turno import Turno
from app.models.TurnoLaboral import TurnoLaboral
from app.models.Usuario import Usuario
from app.models.Venta import Venta
from app.models.Zona import Zona

__all__ = [
    'AsignacionTurno',
    'Caja',
    'CapturaComprobante',
    'Carro',
    'Cliente',
    'ComprobanteBase',
    'ComprobanteReserva',
    'ComprobanteReservaEntrada',
    'DetalleReserva',
    'DetalleReservaEntrada',
    'DetalleVenta',
    'Dinosaurio',
    'Flota',
    'LecturaFlota',
    'Mantenimiento',
    'Moto',
    'MovimientoCaja',
    'Pago',
    'PaqueteTarifa',
    'Repuesto',
    'Reserva',
    'ReservaEntrada',
    'Rol',
    'Sucursal',
    'Ticket',
    'Turno',
    'TurnoLaboral',
    'Usuario',
    'Venta',
    'Zona',
]
