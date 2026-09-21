from sqlalchemy import text

from app.database import db


class DetalleReserva(db.Model):
    __tablename__ = 'detalles_reserva'

    id_detalle = db.Column(db.Integer, primary_key=True)
    id_reserva = db.Column(
        db.Integer, db.ForeignKey('reservas.id_reserva'), nullable=False
    )
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False)
    id_franja = db.Column(db.Integer, db.ForeignKey('franjas.id_franja'), nullable=False)
    # False cuando la reserva se cancela o se rechaza (libera la franja)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    flota = db.relationship('Flota', lazy=True)

    # Garantía en base de datos contra la doble reserva: una franja solo
    # puede tener UN detalle activo.
    __table_args__ = (
        db.Index(
            'uq_detalle_franja_activo', 'id_franja', unique=True,
            postgresql_where=text('activo'), sqlite_where=text('activo'),
        ),
    )
