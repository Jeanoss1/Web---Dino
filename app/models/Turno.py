from app.database import db


class Turno(db.Model):
    __tablename__ = 'turnos'

    id_turno = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False)
    horario_inicio = db.Column(db.DateTime, nullable=False)
    horario_fin = db.Column(db.DateTime, nullable=False)
    estado = db.Column(db.String(20), default='disponible')
    capacidad = db.Column(db.Integer, default=1)

    id_flota = db.Column(
        db.Integer, db.ForeignKey('flota.id_flota'), nullable=False, index=True
    )

    # Para /api/turnos, que filtra por estado y por día
    __table_args__ = (db.Index('ix_turnos_estado_fecha', 'estado', 'fecha'),)

    # Un turno aparece en muchos detalles de reserva (crea DetalleReserva.turno)
    detalles = db.relationship('DetalleReserva', backref='turno', lazy=True)