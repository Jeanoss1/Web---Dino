from datetime import datetime

from app.database import db


class RegistroUso(db.Model):
    """Tiempo REAL que se usó un vehículo (hora de inicio y de fin)."""
    __tablename__ = 'registros_uso'

    id_uso = db.Column(db.Integer, primary_key=True)
    id_detalle_venta = db.Column(
        db.Integer, db.ForeignKey('detalles_venta.id_detalle_venta'), nullable=False
    )
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False)
    id_sucursal = db.Column(
        db.Integer, db.ForeignKey('sucursales.id_sucursal'), nullable=False
    )
    id_usuario = db.Column(          # cajero que registró el uso
        db.Integer, db.ForeignKey('usuarios.id_usuario'), nullable=False, index=True
    )
    hora_inicio = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    hora_fin = db.Column(db.DateTime)
    minutos_usados = db.Column(db.Integer)
    estado = db.Column(db.String(20), default='en_curso', index=True)   # en_curso / finalizado

    # Hora en que el alquiler debe terminar solo (inicio + bloques x 12 min)
    hora_fin_prevista = db.Column(db.DateTime, index=True)
    minutos_previstos = db.Column(db.Integer)
    finalizado_por = db.Column(db.String(20))     # automatico / cajero
    motivo_fin = db.Column(db.String(200))        # motivo si el cajero finalizó antes

    # Lo que este uso sumó al contador del sistema (minutos o 1 encendido) y cuándo
    contador_delta = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    contador_fecha = db.Column(db.DateTime, index=True)

    flota = db.relationship('Flota')
    usuario = db.relationship('Usuario')
