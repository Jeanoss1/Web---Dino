from app.database import db


class Mantenimiento(db.Model):
    __tablename__ = 'mantenimientos'

    id_mantenimiento = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    fecha_inicio = db.Column(db.DateTime, nullable=False)
    fecha_fin = db.Column(db.DateTime)
    observacion = db.Column(db.String(300))
    estado = db.Column(db.String(20), default='pendiente')

    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False)
    # Un mantenimiento utiliza 0 o 1 repuesto (crea Repuesto.mantenimientos)
    id_repuesto = db.Column(db.Integer, db.ForeignKey('repuestos.id_repuesto'))