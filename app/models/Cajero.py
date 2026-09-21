from app.database import db

HORAS_POR_TIPO = {'completo': 8, 'medio': 4}


class Cajero(db.Model):
    """Perfil del cajero: pertenece a UNA sede y tiene un tipo de turno
    (tiempo completo = 8 h, medio tiempo = 4 h)."""
    __tablename__ = 'cajeros'

    id_cajero = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id_usuario'), unique=True, nullable=False
    )
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False
    )
    tipo_turno = db.Column(db.String(20), nullable=False, default='completo')
    estado = db.Column(db.String(20), default='activo')

    usuario = db.relationship(
        'Usuario', backref=db.backref('cajero', uselist=False)
    )
    sucursal = db.relationship('Sucursal', backref='cajeros')

    @property
    def horas_turno(self):
        return HORAS_POR_TIPO.get(self.tipo_turno, 8)

    @property
    def nombre(self):
        return self.usuario.nombre_completo
