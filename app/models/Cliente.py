from app.database import db


class Cliente(db.Model):
    __tablename__ = 'clientes'

    id_cliente = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(12), nullable=False, unique=True)
    telefono = db.Column(db.String(15))
    correo = db.Column(db.String(120))
    estado = db.Column(db.String(20), default='activo')

    # Un cliente realiza muchas reservas (crea Reserva.cliente)
    reservas = db.relationship('Reserva', backref='cliente', lazy=True)