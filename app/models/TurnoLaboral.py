from app.database import db


class TurnoLaboral(db.Model):
    """Plantilla de horario LABORAL de un cajero (ej. 'Mañana completo
    08:00-16:00'). No confundir con `Turno`, que es el horario reservable
    de una unidad de flota."""
    __tablename__ = 'turnos_laborales'

    id_turno_laboral = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False, unique=True)
    tipo = db.Column(db.String(20), nullable=False, default='completo')  # completo / medio
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    estado = db.Column(db.String(20), default='activo')
