"""Importa todos los modelos para que SQLAlchemy y Flask-Migrate los conozcan."""
from app.models.Rol import Rol
from app.models.usuario import Usuario
from app.models.Sucursal import Sucursal
from app.models.Cliente import Cliente
from app.models.Cajero import Cajero
from app.models.Turno import Turno, AsignacionTurno
from app.models.Tarifa import Tarifa
from app.models.Flota import Flota, Dinosaurio, Carro, Moto, Otros
from app.models.Franja import Franja
from app.models.Reserva import Reserva
from app.models.DetalleReserva import DetalleReserva
from app.models.ComprobanteReserva import ComprobanteReserva
from app.models.Venta import Venta
from app.models.DetalleVenta import DetalleVenta
from app.models.Pago import Pago
from app.models.Ticket import Ticket
from app.models.Caja import Caja
from app.models.MovimientoCaja import MovimientoCaja
from app.models.RegistroUso import RegistroUso
from app.models.LecturaCaja import LecturaCaja, Parametro
from app.models.Repuesto import Repuesto
from app.models.Mantenimiento import Mantenimiento

__all__ = [
    'Rol', 'Usuario', 'Sucursal', 'Cliente', 'Cajero', 'Turno', 'AsignacionTurno',
    'Tarifa', 'Flota', 'Dinosaurio', 'Carro', 'Moto', 'Otros', 'Franja', 'Reserva',
    'DetalleReserva', 'ComprobanteReserva', 'Venta', 'DetalleVenta', 'Pago',
    'Ticket', 'Caja', 'MovimientoCaja', 'RegistroUso', 'LecturaCaja', 'Parametro', 'Repuesto', 'Mantenimiento',
]
