from app.database import db
from app.tiempo import ahora


class CapturaComprobante(db.Model):
    """Copia en la BD de cada captura de pago guardada en disco.

    En Render (plan gratuito) el disco del servidor se borra en cada
    despliegue o reinicio; la BD no. Si el archivo ya no está en disco,
    la captura se sirve desde aquí.
    """
    __tablename__ = 'capturas_comprobante'

    nombre = db.Column(db.String(200), primary_key=True)   # mismo nombre que ComprobanteBase.archivo
    tipo_mime = db.Column(db.String(50), nullable=False)
    datos = db.Column(db.LargeBinary, nullable=False)
    fecha = db.Column(db.DateTime, default=ahora)
