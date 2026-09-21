from app.database import db


class Flota(db.Model):
    """Clase base. Dinosaurio, Carro, Moto y Otros heredan de ella.
    La columna `tipo` indica de qué subclase es cada fila."""
    __tablename__ = 'flota'

    id_flota = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    modelo = db.Column(db.String(100))
    estado = db.Column(db.String(30), default='disponible')
    precio_hora = db.Column(db.Numeric(10, 2), default=0)
    ciclos_uso = db.Column(db.Integer, default=0)

    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False
    )

    # Una flota programa muchos turnos (crea Turno.flota)
    turnos = db.relationship('Turno', backref='flota', lazy=True)
    # Una flota puede tener muchos mantenimientos (crea Mantenimiento.flota)
    mantenimientos = db.relationship('Mantenimiento', backref='flota', lazy=True)

    __mapper_args__ = {
        'polymorphic_on': tipo,
        'polymorphic_identity': 'flota',
    }


class Dinosaurio(Flota):
    __tablename__ = 'dinosaurios'

    id_flota = db.Column(
        db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True
    )
    especie = db.Column(db.String(100))

    __mapper_args__ = {'polymorphic_identity': 'dinosaurio'}


class Carro(Flota):
    __tablename__ = 'carros'

    id_flota = db.Column(
        db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True
    )
    velocidad = db.Column(db.String(50))

    __mapper_args__ = {'polymorphic_identity': 'carro'}


class Moto(Flota):
    __tablename__ = 'motos'

    id_flota = db.Column(
        db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True
    )
    cilindrada = db.Column(db.String(50))

    __mapper_args__ = {'polymorphic_identity': 'moto'}


class Otros(Flota):
    __tablename__ = 'otros'

    id_flota = db.Column(
        db.Integer, db.ForeignKey('flota.id_flota'), primary_key=True
    )
    descripcion = db.Column(db.String(200))

    __mapper_args__ = {'polymorphic_identity': 'otros'}