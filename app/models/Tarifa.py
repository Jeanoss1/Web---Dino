from datetime import datetime

from app.database import db


class Tarifa(db.Model):
    """Precio por bloque de tiempo, igual para todas las atracciones.
    Solo la edita el administrador."""
    __tablename__ = 'tarifas'

    id_tarifa = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(60), nullable=False, default='Estándar')
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    minutos = db.Column(db.Integer, nullable=False)
    activa = db.Column(db.Boolean, default=True)
    actualizado_en = db.Column(db.DateTime, default=datetime.now)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
