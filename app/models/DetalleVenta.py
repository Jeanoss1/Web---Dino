from app.database import db


class DetalleVenta(db.Model):
    __tablename__ = 'detalles_venta'

    id_detalle_venta = db.Column(db.Integer, primary_key=True)
    precio = db.Column(db.Numeric(10, 2), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    id_venta = db.Column(db.Integer, db.ForeignKey('ventas.id_venta'), nullable=False)
    # Relación 1 a 1 con Pago (crea DetalleVenta.pago). Nullable: se puede
    # crear el detalle antes de registrar el pago.
    id_pago = db.Column(db.Integer, db.ForeignKey('pagos.id_pago'), unique=True)

    def calcular_subtotal(self):
        self.subtotal = self.precio * self.cantidad
        return self.subtotal