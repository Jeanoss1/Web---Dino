from app.database import db


class Repuesto(db.Model):
    __tablename__ = 'repuestos'

    id_repuesto = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    stock = db.Column(db.Integer, default=0)
    stock_minimo = db.Column(db.Integer, default=0)
    estado = db.Column(db.String(20), default='activo')

    mantenimientos = db.relationship('Mantenimiento', backref='repuesto', lazy=True)

    @property
    def necesita_reposicion(self):
        return self.stock <= self.stock_minimo