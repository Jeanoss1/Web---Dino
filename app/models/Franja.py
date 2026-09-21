from app.database import db


class Franja(db.Model):
    """Horario reservable de una unidad de flota (antes llamado `Turno`).
    Cada franja dura un bloque de la tarifa (12 minutos)."""
    __tablename__ = 'franjas'

    id_franja = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    horario_inicio = db.Column(db.DateTime, nullable=False)
    horario_fin = db.Column(db.DateTime, nullable=False)
    # disponible / reservada / ocupada (venta presencial)
    estado = db.Column(db.String(20), default='disponible')
    capacidad = db.Column(db.Integer, default=1)

    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False)

    detalles = db.relationship('DetalleReserva', backref='franja', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('id_flota', 'horario_inicio', name='uq_franja_flota_inicio'),
    )
