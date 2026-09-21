from datetime import datetime

from app.database import db


class Reserva(db.Model):
    __tablename__ = 'reservas'

    id_reserva = db.Column(db.Integer, primary_key=True)
    fecha_reserva = db.Column(db.DateTime, default=datetime.now)
    estado = db.Column(db.String(20), default='pendiente')
    cantidad_personas = db.Column(db.Integer, default=1)
    total = db.Column(db.Numeric(10, 2), default=0)

    id_cliente = db.Column(
        db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False
    )

    # Una reserva incluye uno o más detalles (crea DetalleReserva.reserva)
    detalles = db.relationship(
        'DetalleReserva', backref='reserva', lazy=True,
        cascade='all, delete-orphan'
    )