from app.database import db
from app.tiempo import ahora


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id_ticket = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), nullable=False, unique=True)
    fecha_emision = db.Column(db.DateTime, default=ahora)
    estado = db.Column(db.String(20), default='emitido')

    # Nullable: un ticket puede venir de un pago o solo de un movimiento de caja
    id_pago = db.Column(db.Integer, db.ForeignKey('pagos.id_pago'), unique=True)

    # Ticket de una reserva en línea: se emite cuando el cajero acepta su pago (HU03)
    id_reserva = db.Column(db.Integer, db.ForeignKey('reservas.id_reserva'), unique=True)
    reserva = db.relationship('Reserva', backref=db.backref('ticket', uselist=False), lazy=True)

    # Uso del ticket en caja (HU05): estado pasa de 'emitido' a 'usado'
    fecha_uso = db.Column(db.DateTime)
    id_validador = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))

    # Un ticket puede estar en varios movimientos de caja (crea MovimientoCaja.ticket)
    movimientos = db.relationship('MovimientoCaja', backref='ticket', lazy=True)