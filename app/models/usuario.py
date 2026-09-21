from app.database import db


class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id_usuario = db.Column(db.Integer, primary_key=True)
    id_rol = db.Column(db.Integer, db.ForeignKey('roles.id_rol'), nullable=False)

    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    contrasena = db.Column(db.String(255), nullable=False)   # hash de werkzeug
    estado = db.Column(db.Boolean, default=True)

    # `rol` llega por el backref de Rol.usuarios; `cajero` y `cliente` por sus modelos.

    @property
    def rol_nombre(self):
        return self.rol.nombre if self.rol else None

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'

    def __repr__(self):
        return f'<Usuario {self.nombre} {self.apellido}>'
