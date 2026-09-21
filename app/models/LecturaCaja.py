from datetime import datetime

from app.database import db


class Parametro(db.Model):
    """Ajustes que edita el administrador (p. ej. tolerancias de los contadores)."""
    __tablename__ = 'parametros'

    clave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(db.String(60), nullable=False)


class LecturaCaja(db.Model):
    """Lectura MANUAL del contador de una atracción que registra el cajero al abrir
    y al cerrar su caja. Se guarda aparte del contador que calcula el sistema."""
    __tablename__ = 'lecturas_caja'

    id_lectura = db.Column(db.Integer, primary_key=True)
    id_caja = db.Column(db.Integer, db.ForeignKey('cajas.id_caja'), nullable=False, index=True)
    id_flota = db.Column(db.Integer, db.ForeignKey('flota.id_flota'), nullable=False, index=True)
    tipo_contador = db.Column(db.String(15), nullable=False)          # minutos / encendidos

    # Apertura
    lectura_inicial = db.Column(db.Integer, nullable=False)
    sugerida = db.Column(db.Integer)                 # lectura del último cierre (precargada)
    es_primera = db.Column(db.Boolean, default=False)  # primera vez que se usa el sistema
    motivo_apertura = db.Column(db.String(200))
    alerta_apertura = db.Column(db.Boolean, default=False)

    # Cierre
    lectura_final = db.Column(db.Integer)
    estado_unidad = db.Column(db.String(30))         # si se omitió: mantenimiento / inactivo
    observacion = db.Column(db.String(300))

    # Resultado del cuadre (se calcula al cerrar)
    uso_real = db.Column(db.Integer)                 # lectura final - lectura inicial
    contador_sistema = db.Column(db.Integer)         # lo que el sistema sumó en el turno
    vendido = db.Column(db.Integer)                  # minutos o encendidos vendidos
    dif_sistema = db.Column(db.Integer)              # uso real - contador del sistema
    dif_vendido = db.Column(db.Integer)              # uso real - vendido
    alerta = db.Column(db.Boolean, default=False, index=True)
    alertas = db.Column(db.String(600))

    # Ajuste del administrador sobre un cierre ya cerrado (exige justificación)
    nota_admin = db.Column(db.String(300))
    ajustado_por = db.Column(db.Integer, db.ForeignKey('usuarios.id_usuario'))
    ajustado_en = db.Column(db.DateTime)

    caja = db.relationship('Caja', backref=db.backref('lecturas', lazy=True))
    flota = db.relationship('Flota')
    ajustador = db.relationship('Usuario', foreign_keys=[ajustado_por])

    __table_args__ = (
        db.UniqueConstraint('id_caja', 'id_flota', name='uq_lectura_caja_flota'),
    )
