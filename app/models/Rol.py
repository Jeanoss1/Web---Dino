from app.database import db

class Rol(db.Model):
    __tablename__ = 'roles'

    id_rol = db.Column(db.Integer, primary_key=True)  # <-- Debe ser id_rol
    nombre = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.String(200))

    # backref='rol' crea automáticamente el atributo `usuario.rol`
    # (usado en auth_controller.py para leer usuario.rol.nombre).
    # No declares otra relación desde Usuario.py: bastaría con esta,
    # declarada de un solo lado, para tener ambos sentidos.
    usuarios = db.relationship('Usuario', backref='rol', lazy=True)

    def __repr__(self):
        return f'<Rol {self.nombre}>'