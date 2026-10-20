from app.database import db


class AsignacionTurno(db.Model):
    """Qué TurnoLaboral trabaja un cajero (`id_usuario`) en una fecha
    puntual. Sin asignación para un día = libre ese día."""
    __tablename__ = 'asignaciones_turno'

    id_asignacion = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False, index=True
    )
    id_turno_laboral = db.Column(
        db.Integer, db.ForeignKey('turnos_laborales.id_turno_laboral'), nullable=False
    )
    fecha = db.Column(db.Date, nullable=False, index=True)

    turno_laboral = db.relationship('TurnoLaboral', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('id_usuario', 'fecha', name='uq_asignacion_usuario_fecha'),
    )
