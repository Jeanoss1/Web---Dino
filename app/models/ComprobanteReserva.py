from datetime import datetime

from app.database import db


class ComprobanteReserva(db.Model):
    """Captura del pago (Yape) que sube el cliente para una reserva.
    Una reserva puede tener varios: si el cajero rechaza uno, el cliente sube otro."""
    __tablename__ = 'comprobantes_reserva'

    id_comprobante = db.Column(db.Integer, primary_key=True)
    id_reserva = db.Column(
        db.Integer, db.ForeignKey('reservas.id_reserva'), nullable=False
    )
    metodo_pago = db.Column(db.String(20), default='yape')
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    archivo = db.Column(db.String(200), nullable=False)      # nombre del archivo guardado
    hash_archivo = db.Column(db.String(64), index=True)      # detecta capturas repetidas
    fecha_subida = db.Column(db.DateTime, default=datetime.now)

    estado = db.Column(db.String(20), default='por_validar')  # por_validar / aceptado / rechazado
    id_validador = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    fecha_validacion = db.Column(db.DateTime)
    motivo_rechazo = db.Column(db.String(200))

    reserva = db.relationship(
        'Reserva',
        backref=db.backref(
            'comprobantes', lazy=True,
            order_by='ComprobanteReserva.id_comprobante',
        ),
    )