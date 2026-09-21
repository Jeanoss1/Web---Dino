from app.database import db


class DetalleVenta(db.Model):
    __tablename__ = 'detalles_venta'

    id_detalle_venta = db.Column(db.Integer, primary_key=True)
    precio = db.Column(db.Numeric(10, 2), nullable=False)       # precio por bloque
    cantidad = db.Column(db.Integer, nullable=False, default=1)  # bloques vendidos
    minutos = db.Column(db.Integer, nullable=False, default=0)   # cantidad x minutos por bloque
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    fecha_servicio = db.Column(db.Date, nullable=False, index=True)

    id_venta = db.Column(db.Integer, db.ForeignKey('ventas.id_venta'), nullable=False)
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False)
    id_detalle_reserva = db.Column(
        db.Integer, db.ForeignKey('detalles_reserva.id_detalle')
    )
    id_pago = db.Column(db.Integer, db.ForeignKey('pagos.id_pago'), unique=True)

    flota = db.relationship('Flota')
    usos = db.relationship('RegistroUso', backref='detalle_venta', lazy=True)

    def calcular_subtotal(self):
        self.subtotal = self.precio * self.cantidad
        return self.subtotal

    @property
    def minutos_usados(self):
        return sum(u.minutos_usados or 0 for u in self.usos if u.estado == 'finalizado')

    @property
    def uso_en_curso(self):
        return next((u for u in self.usos if u.estado == 'en_curso'), None)
