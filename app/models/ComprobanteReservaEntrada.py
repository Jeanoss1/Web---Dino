from app.database import db
from app.models.ComprobanteBase import ComprobanteBase


class ComprobanteReservaEntrada(ComprobanteBase, db.Model):
    """Captura del pago (Yape) que sube el cliente para una ReservaEntrada.
    Espejo de ComprobanteReserva."""
    __tablename__ = 'comprobantes_reserva_entrada'

    id_reserva_entrada = db.Column(
        db.Integer, db.ForeignKey('reservas_entrada.id_reserva_entrada'),
        nullable=False, index=True
    )

    reserva_entrada = db.relationship(
        'ReservaEntrada',
        backref=db.backref(
            'comprobantes', lazy=True,
            order_by='ComprobanteReservaEntrada.id_comprobante',
        ),
    )
