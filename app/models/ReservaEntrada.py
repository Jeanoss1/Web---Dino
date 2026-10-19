from datetime import datetime

from app.database import db


class ReservaEntrada(db.Model):
    """Reserva online de entrada por tiempo (Hoyos Rubio y sedes futuras del
    mismo modelo). Espejo de Reserva, pero sus detalles apuntan a un
    PaqueteTarifa en vez de a flota+turno."""
    __tablename__ = 'reservas_entrada'

    id_reserva_entrada = db.Column(db.Integer, primary_key=True)
    fecha_reserva = db.Column(db.DateTime, default=datetime.now)
    estado = db.Column(db.String(20), default='pendiente', index=True)
    total = db.Column(db.Numeric(10, 2), default=0)

    id_cliente = db.Column(
        db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False, index=True
    )
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False
    )

    # Una reserva incluye uno o más detalles (crea DetalleReservaEntrada.reserva_entrada)
    detalles = db.relationship(
        'DetalleReservaEntrada', backref='reserva_entrada', lazy=True,
        cascade='all, delete-orphan'
    )

    # Para acceder al dueño de la reserva: reserva_entrada.cliente
    cliente = db.relationship(
        'Cliente', backref='reservas_entrada', lazy=True
    )
