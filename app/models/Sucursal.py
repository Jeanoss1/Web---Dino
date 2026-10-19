from app.database import db


class Sucursal(db.Model):
    __tablename__ = 'sucursales'

    id_sucursal = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    estado = db.Column(db.String(20), default='activa')

    # Sedes de entrada por tiempo (ej. Hoyos Rubio): monto configurable que se
    # cobra si el niño no sale cuando se le llama. NULL = sede sin esta regla.
    monto_adicional_exceso = db.Column(db.Numeric(10, 2))

    # Una sucursal tiene muchos elementos de flota (crea Flota.sucursal)
    flota = db.relationship('Flota', backref='sucursal', lazy=True)

    # Una sucursal de entrada por tiempo tiene una o más zonas (crea Zona.sucursal)
    zonas = db.relationship('Zona', backref='sucursal', lazy=True)