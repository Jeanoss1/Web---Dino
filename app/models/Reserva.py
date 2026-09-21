from datetime import datetime

from app.database import db

# pendiente_pago -> pago_en_revision -> confirmada -> completada
#                                    \-> rechazada
# pendiente_pago -> cancelada (por el cliente o por vencer el plazo de pago)
ESTADOS_RESERVA = (
    'pendiente_pago', 'pago_en_revision', 'confirmada',
    'rechazada', 'cancelada', 'completada',
)
ESTADOS_ACTIVOS = ('pendiente_pago', 'pago_en_revision', 'confirmada')


class Reserva(db.Model):
    __tablename__ = 'reservas'

    id_reserva = db.Column(db.Integer, primary_key=True)
    fecha_reserva = db.Column(db.DateTime, default=datetime.now)
    estado = db.Column(db.String(20), default='pendiente_pago', index=True)
    cantidad_personas = db.Column(db.Integer, default=1)
    total = db.Column(db.Numeric(10, 2), default=0)
    # Plazo para pagar; pasado ese momento la reserva se cancela sola
    vence_en = db.Column(db.DateTime)

    id_cliente = db.Column(
        db.Integer, db.ForeignKey('clientes.id_cliente'), nullable=False
    )
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False
    )

    sucursal = db.relationship('Sucursal')
    detalles = db.relationship(
        'DetalleReserva', backref='reserva', lazy=True,
        cascade='all, delete-orphan'
    )
