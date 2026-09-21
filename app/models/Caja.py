from app.database import db


class Caja(db.Model):
    """Caja de UN cajero en UNA sede. Al cerrarla se guarda el cuadre."""
    __tablename__ = 'cajas'

    id_caja = db.Column(db.Integer, primary_key=True)
    fecha_apertura = db.Column(db.DateTime, nullable=False)
    fecha_cierre = db.Column(db.DateTime)
    monto_inicial = db.Column(db.Numeric(10, 2), default=0)
    monto_final = db.Column(db.Numeric(10, 2))                 # efectivo contado al cerrar
    estado = db.Column(db.String(20), default='abierta')

    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False, index=True
    )
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False
    )

    # Cuadre guardado al cerrar
    efectivo_esperado = db.Column(db.Numeric(10, 2))
    diferencia = db.Column(db.Numeric(10, 2))
    total_efectivo = db.Column(db.Numeric(10, 2))
    total_yape = db.Column(db.Numeric(10, 2))
    minutos_vendidos = db.Column(db.Integer)
    minutos_usados = db.Column(db.Integer)
    observacion = db.Column(db.String(300))

    usuario = db.relationship('Usuario')
    sucursal = db.relationship('Sucursal')
    movimientos = db.relationship('MovimientoCaja', backref='caja', lazy=True)
