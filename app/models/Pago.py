from datetime import datetime

from app.database import db


class Pago(db.Model):
    __tablename__ = 'pagos'

    id_pago = db.Column(db.Integer, primary_key=True)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    metodo_pago = db.Column(db.String(30))
    fecha_pago = db.Column(db.DateTime, default=datetime.now)
    estado = db.Column(db.String(20), default='pendiente')

    # 1 a 1 con DetalleVenta (crea DetalleVenta.pago)
    detalle_venta = db.relationship(
        'DetalleVenta', backref='pago', uselist=False, lazy=True
    )
    # Un pago genera un ticket (crea Ticket.pago)
    ticket = db.relationship('Ticket', backref='pago', uselist=False, lazy=True)