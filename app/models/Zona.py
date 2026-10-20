from app.database import db


class Zona(db.Model):
    """Área de una sede que vende entrada por tiempo (ej. el inflable o el
    arenero de Hoyos Rubio), en vez de alquilar unidades de flota."""
    __tablename__ = 'zonas'

    id_zona = db.Column(db.Integer, primary_key=True)
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False, index=True
    )
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(300))
    estado = db.Column(db.String(20), default='activa')

    # Una zona tiene uno o más paquetes de tarifa (crea PaqueteTarifa.zona)
    paquetes = db.relationship(
        'PaqueteTarifa', backref='zona', lazy=True,
        order_by='PaqueteTarifa.orden',
    )
