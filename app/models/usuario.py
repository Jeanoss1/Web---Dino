from app.database import db

class Usuario(db.Model):
    __tablename__ = 'usuarios'

    # Cambiamos idUsuario por id_usuario
    id_usuario = db.Column(db.Integer, primary_key=True)
    # Cambiamos idRol por id_rol para que coincida con la tabla roles
    id_rol = db.Column(db.Integer, db.ForeignKey('roles.id_rol'), nullable=False)

    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    contrasena = db.Column(db.String(200), nullable=False)
    estado = db.Column(db.Boolean, default=True)

    # NOTA: no se declara relationship aquí. El atributo `rol` llega
    # automáticamente por el backref definido en Rol.py
    # (usuarios = db.relationship('Usuario', backref='rol', ...)).
    # Declararlo también aquí produciría un backref duplicado.

    def __repr__(self):
        return f'<Usuario {self.nombre} {self.apellido}>'