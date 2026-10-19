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

    # Entradas por tiempo (ej. Hoyos Rubio): qué paquete se vendió y cuándo
    # entró el niño, para el temporizador de caja. Nullable: ventas normales
    # (precio/cantidad libres) no usan estas columnas.
    id_paquete = db.Column(db.Integer, db.ForeignKey('paquetes_tarifa.id_paquete'))
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'))
    hora_inicio = db.Column(db.DateTime)
    hora_fin = db.Column(db.DateTime)  # cuándo salió realmente (cuadre de minutos)
    exceso_cobrado = db.Column(db.Boolean, default=False)

    # Para acceder al paquete vendido: detalle.paquete
    paquete = db.relationship('PaqueteTarifa', lazy=True)
    # Para acceder a la unidad de flota alquilada: detalle.flota
    flota = db.relationship('Flota', lazy=True)

    def calcular_subtotal(self):
        self.subtotal = self.precio * self.cantidad
        return self.subtotal