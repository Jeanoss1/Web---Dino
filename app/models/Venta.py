from datetime import datetime

from app.database import db


class Venta(db.Model):
    __tablename__ = 'ventas'

    id_venta = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.now)
    total = db.Column(db.Numeric(10, 2), default=0)
    tipo_pago = db.Column(db.String(30))
    estado = db.Column(db.String(20), default='pendiente')

    # OJO: ajusta 'usuarios.id_usuario' si tu tabla o columna se llaman distinto
    id_usuario = db.Column(
        db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False
    )

    # De qué sede es la venta (para reportes). Nullable: las ventas antiguas
    # no lo tenían.
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal')
    )

    # Una venta contiene uno o más detalles (crea DetalleVenta.venta)
    detalles = db.relationship(
        'DetalleVenta', backref='venta', lazy=True,
        cascade='all, delete-orphan'
    )