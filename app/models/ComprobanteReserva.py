from app.database import db
from app.models.ComprobanteBase import ComprobanteBase


class ComprobanteReserva(ComprobanteBase, db.Model):
    """Captura del pago (Yape) que sube el cliente para una reserva.
    Una reserva puede tener varios: si el cajero rechaza uno, el cliente sube otro."""
    __tablename__ = 'comprobantes_reserva'

    id_reserva = db.Column(
        db.Integer, db.ForeignKey('reservas.id_reserva'), nullable=False, index=True
    )

    reserva = db.relationship(
        'Reserva',
        backref=db.backref(
            'comprobantes', lazy=True,
            order_by='ComprobanteReserva.id_comprobante',
        ),
    )
