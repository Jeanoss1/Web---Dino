from app.database import db


class DetalleReservaEntrada(db.Model):
    """Una línea de una ReservaEntrada: un paquete y la cantidad de niños
    (o adultos, para el Pack Guía)."""
    __tablename__ = 'detalles_reserva_entrada'

    id_detalle = db.Column(db.Integer, primary_key=True)

    id_reserva_entrada = db.Column(
        db.Integer, db.ForeignKey('reservas_entrada.id_reserva_entrada'),
        nullable=False, index=True
    )
    id_paquete = db.Column(
        db.Integer, db.ForeignKey('paquetes_tarifa.id_paquete'), nullable=False
    )
    cantidad = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # Se llenan cuando el cajero marca el ingreso físico del niño (el cliente
    # pudo reservar días antes; el temporizador arranca recién al entrar).
    hora_inicio = db.Column(db.DateTime)
    hora_fin = db.Column(db.DateTime)  # cuándo salió realmente (cuadre de minutos)
    exceso_cobrado = db.Column(db.Boolean, default=False)

    # Para acceder al paquete reservado: detalle.paquete
    paquete = db.relationship('PaqueteTarifa', lazy=True)
