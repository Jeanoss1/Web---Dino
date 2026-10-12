from app.database import db


class DetalleReserva(db.Model):
    __tablename__ = 'detalles_reserva'

    id_detalle = db.Column(db.Integer, primary_key=True)

    id_reserva = db.Column(
        db.Integer, db.ForeignKey('reservas.id_reserva'), nullable=False, index=True
    )
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False)
    id_turno = db.Column(
        db.Integer, db.ForeignKey('turnos.id_turno'), nullable=False, index=True
    )

    # Para acceder a la unidad reservada: detalle.flota
    flota = db.relationship('Flota', lazy=True)