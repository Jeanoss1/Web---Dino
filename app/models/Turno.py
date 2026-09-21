from datetime import date, datetime

from app.database import db


class Turno(db.Model):
    """Turno LABORAL del cajero (completo = 8 h, medio = 4 h).
    El horario de una unidad de flota se llama `Franja`."""
    __tablename__ = 'turnos'

    id_turno = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(60), nullable=False, unique=True)
    tipo = db.Column(db.String(20), nullable=False)          # completo / medio
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fin = db.Column(db.Time, nullable=False)
    estado = db.Column(db.String(20), default='activo')

    @property
    def horas(self):
        ini = datetime.combine(date.today(), self.hora_inicio)
        fin = datetime.combine(date.today(), self.hora_fin)
        return round((fin - ini).total_seconds() / 3600, 2)

    @property
    def etiqueta(self):
        return f'{self.nombre} ({self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M})'


class AsignacionTurno(db.Model):
    """Qué turno trabaja cada cajero cada día. Se carga cada semana.
    Si un día no tiene asignación, el cajero descansa."""
    __tablename__ = 'asignaciones_turno'

    id_asignacion = db.Column(db.Integer, primary_key=True)
    id_cajero = db.Column(
        db.Integer, db.ForeignKey('cajeros.id_cajero'), nullable=False
    )
    id_turno = db.Column(db.Integer, db.ForeignKey('turnos.id_turno'), nullable=False)
    fecha = db.Column(db.Date, nullable=False)

    cajero = db.relationship('Cajero', backref='asignaciones')
    turno = db.relationship('Turno')

    __table_args__ = (
        db.UniqueConstraint('id_cajero', 'fecha', name='uq_asignacion_cajero_fecha'),
    )
