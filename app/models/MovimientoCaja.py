from datetime import datetime

from app.database import db


class MovimientoCaja(db.Model):
    __tablename__ = 'movimientos_caja'

    id_movimiento = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # ingreso / egreso
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)
    descripcion = db.Column(db.String(200))

    id_caja = db.Column(db.Integer, db.ForeignKey('cajas.id_caja'), nullable=False)
    id_ticket = db.Column(db.Integer, db.ForeignKey('tickets.id_ticket'))