from app.database import db


class Caja(db.Model):
    __tablename__ = 'cajas'

    id_caja = db.Column(db.Integer, primary_key=True)
    fecha_apertura = db.Column(db.DateTime, nullable=False)
    fecha_cierre = db.Column(db.DateTime)
    monto_inicial = db.Column(db.Numeric(10, 2), default=0)
    monto_final = db.Column(db.Numeric(10, 2))
    estado = db.Column(db.String(20), default='abierta')

    # Quién la abrió y en qué sede, para saber a quién pedirle que la
    # cierre antes de reasignarlo y para exigir lecturas solo en sedes con flota.
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=True)
    id_sucursal = db.Column(db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=True)

    # Una caja registra muchos movimientos (crea MovimientoCaja.caja)
    movimientos = db.relationship('MovimientoCaja', backref='caja', lazy=True)