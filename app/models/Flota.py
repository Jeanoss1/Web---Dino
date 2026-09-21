from app.database import db

TIPOS_CONTADOR = ('minutos', 'encendidos')
# Por defecto: los dinosaurios cuentan minutos; carros y motos, encendidos.
CONTADOR_POR_TIPO = {'dinosaurio': 'minutos', 'carro': 'encendidos', 'moto': 'encendidos', 'otros': 'minutos'}


def _contador_por_defecto(contexto):
    return CONTADOR_POR_TIPO.get(contexto.get_current_parameters().get('tipo'), 'minutos')


class Flota(db.Model):
    """Clase base. Dinosaurio, Carro, Moto y Otros heredan de ella.
    La columna `tipo` indica de qué subclase es cada fila.
    El precio ya no se guarda aquí: sale de la tabla `tarifas`."""
    __tablename__ = 'flota'

    id_flota = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    modelo = db.Column(db.String(100))
    estado = db.Column(db.String(30), default='disponible')   # disponible / mantenimiento / inactivo
    ciclos_uso = db.Column(db.Integer, default=0)

    # Contador de la atraccion: "minutos" acumulados o "encendidos" (veces que se prendio).
    tipo_contador = db.Column(
        db.String(15), nullable=False, default=_contador_por_defecto, server_default='minutos'
    )
    # CONTADOR DEL SISTEMA: lo suma solo el sistema (al finalizar / al iniciar un alquiler).
    contador_sistema = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    # LECTURA MANUAL: la ultima que registro un cajero (contador fisico); se guarda aparte.
    lectura_manual = db.Column(db.Integer)

    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False
    )

    franjas = db.relationship('Franja', backref='flota', lazy=True)
    mantenimientos = db.relationship('Mantenimiento', backref='flota', lazy=True)

    __mapper_args__ = {
        'polymorphic_on': tipo,
        'polymorphic_identity': 'flota',
    }


class Dinosaurio(Flota):
    __tablename__ = 'dinosaurios'
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True)
    especie = db.Column(db.String(100))
    __mapper_args__ = {'polymorphic_identity': 'dinosaurio'}


class Carro(Flota):
    __tablename__ = 'carros'
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True)
    velocidad = db.Column(db.String(50))
    __mapper_args__ = {'polymorphic_identity': 'carro'}


class Moto(Flota):
    __tablename__ = 'motos'
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True)
    cilindrada = db.Column(db.String(50))
    __mapper_args__ = {'polymorphic_identity': 'moto'}


class Otros(Flota):
    __tablename__ = 'otros'
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True)
    descripcion = db.Column(db.String(200))
    __mapper_args__ = {'polymorphic_identity': 'otros'}


CLASES_FLOTA = {
    'dinosaurio': Dinosaurio, 'carro': Carro, 'moto': Moto, 'otros': Otros,
}
