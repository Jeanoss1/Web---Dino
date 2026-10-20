from app.database import db


class PaqueteTarifa(db.Model):
    """Tarifa de una zona: nombre, duración y precio, editables por el
    administrador en vez de quedar fijos en el código.

    tipo: 'individual' / 'pack_friends' / 'pack_escolar' / 'pack_guia' / 'general'
    es_por_ninio: True si `precio` se multiplica por la cantidad (niños o
    adultos); False si `precio` es un monto fijo sin importar la cantidad.
    minimo_cantidad: mínimo de niños/adultos requerido para usar este paquete
    (ej. Pack Friends = 2, Pack Escolar = 15).
    """
    __tablename__ = 'paquetes_tarifa'

    id_paquete = db.Column(db.Integer, primary_key=True)
    id_zona = db.Column(
        db.Integer, db.ForeignKey('zonas.id_zona'), nullable=False, index=True
    )
    nombre = db.Column(db.String(150), nullable=False)
    tipo = db.Column(db.String(30), nullable=False, default='individual')
    duracion_minutos = db.Column(db.Integer)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    es_por_ninio = db.Column(db.Boolean, default=True)
    minimo_cantidad = db.Column(db.Integer, default=1)
    estado = db.Column(db.String(20), default='activa')
    orden = db.Column(db.Integer, default=0)
