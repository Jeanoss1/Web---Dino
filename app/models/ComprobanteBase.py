from datetime import datetime

from sqlalchemy.orm import declared_attr

from app.database import db


class ComprobanteBase:
    """Columnas comunes de los comprobantes de pago (captura de Yape).

    La heredan ComprobanteReserva y ComprobanteReservaEntrada; cada uno define
    su propia tabla, la FK a su reserva y la relación.
    """
    id_comprobante = db.Column(db.Integer, primary_key=True)
    metodo_pago = db.Column(db.String(20), default='yape')
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    archivo = db.Column(db.String(200), nullable=False)      # nombre del archivo guardado
    hash_archivo = db.Column(db.String(64), index=True)      # detecta capturas repetidas
    fecha_subida = db.Column(db.DateTime, default=datetime.now)

    estado = db.Column(db.String(20), default='por_validar')  # por_validar / aceptado / rechazado
    fecha_validacion = db.Column(db.DateTime)
    motivo_rechazo = db.Column(db.String(200))

    @declared_attr
    def id_validador(cls):
        return db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
