from app.database import db


class Caja(db.Model):
    __tablename__ = 'cajas'

    id_caja = db.Column(db.Integer, primary_key=True)
    fecha_apertura = db.Column(db.DateTime, nullable=False)
    fecha_cierre = db.Column(db.DateTime)
    monto_inicial = db.Column(db.Numeric(10, 2), default=0)
    monto_final = db.Column(db.Numeric(10, 2))
    estado = db.Column(db.String(20), default='abierta')

    # Una caja registra muchos movimientos (crea MovimientoCaja.caja)
    movimientos = db.relationship('MovimientoCaja', backref='caja', lazy=True)