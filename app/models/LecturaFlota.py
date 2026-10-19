from datetime import datetime

from app.database import db


class LecturaFlota(db.Model):
    """Lectura manual del contador físico de una unidad de flota, tomada al
    abrir y al cerrar una caja, para compararla contra el contador del
    sistema (ciclos_uso / contador_minutos) y detectar diferencias."""
    __tablename__ = 'lecturas_flota'

    id_lectura = db.Column(db.Integer, primary_key=True)
    id_caja = db.Column(db.Integer, db.ForeignKey('cajas.id_caja'), nullable=False, index=True)
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False)
    momento = db.Column(db.String(20), nullable=False)  # 'apertura' / 'cierre'
    lectura_manual = db.Column(db.Integer, nullable=False)
    contador_sistema = db.Column(db.Integer, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.now)

    flota = db.relationship('Flota', lazy=True)
    caja = db.relationship('Caja', backref='lecturas', lazy=True)

    @property
    def diferencia(self):
        return self.lectura_manual - self.contador_sistema
