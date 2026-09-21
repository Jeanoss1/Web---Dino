from datetime import datetime

from app.database import db


class Venta(db.Model):
    """Toda venta (presencial o proveniente de una reserva pagada por Yape)."""
    __tablename__ = 'ventas'

    id_venta = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now, index=True)
    total = db.Column(db.Numeric(10, 2), default=0)
    tipo_pago = db.Column(db.String(30))                      # efectivo / yape
    estado = db.Column(db.String(20), default='pagada')
    origen = db.Column(db.String(20), default='presencial')   # presencial / reserva

    # Cajero que registró la venta (o que validó el pago Yape de la reserva)
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False, index=True
    )
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False, index=True
    )
    id_reserva = db.Column(
        db.Integer, db.ForeignKey('reservas.id_reserva'), unique=True
    )

    usuario = db.relationship('Usuario')
    sucursal = db.relationship('Sucursal')
    reserva = db.relationship(
        'Reserva', backref=db.backref('venta', uselist=False)
    )
    detalles = db.relationship(
        'DetalleVenta', backref='venta', lazy=True,
        cascade='all, delete-orphan'
    )

    @property
    def minutos(self):
        return sum(d.minutos or 0 for d in self.detalles)
