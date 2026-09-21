from datetime import datetime

from app.database import db


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id_ticket = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False, unique=True)
    fecha_emision = db.Column(db.DateTime, default=datetime.now)
    estado = db.Column(db.String(20), default='emitido')

    # Nullable: un ticket puede venir de un pago o solo de un movimiento de caja
    id_pago = db.Column(db.Integer, db.ForeignKey('pagos.id_pago'), unique=True)

    # Un ticket puede estar en varios movimientos de caja (crea MovimientoCaja.ticket)
    movimientos = db.relationship('MovimientoCaja', backref='ticket', lazy=True)