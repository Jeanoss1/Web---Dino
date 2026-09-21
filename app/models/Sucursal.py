from app.database import db


class Sucursal(db.Model):
    __tablename__ = 'sucursales'

    id_sucursal = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    estado = db.Column(db.String(20), default='activa')      # activa / inactiva

    flota = db.relationship('Flota', backref='sucursal', lazy=True)
