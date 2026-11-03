"""Lógica común de los comprobantes de pago (captura de Yape).

La usan comprobante_controller.py (reservas de flota) y entrada_controller.py
(reservas de entrada por tiempo): ambos flujos validan, guardan y rechazan
las capturas exactamente igual.
"""
import hashlib
import os
import uuid
from datetime import datetime

from flask import current_app, request, session

from app.database import db


def extension_por_firma(cabecera):
    """Detecta el tipo real de imagen por su contenido (no por el nombre)."""
    if cabecera.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if cabecera.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return 'webp'
    return None


def validar_captura(reserva):
    """Revisa que la reserva acepte un comprobante y que la captura enviada
    (campo 'comprobante' del multipart) sea una imagen válida.

    Devuelve (mensaje_de_error, None) o (None, (contenido, extension, huella)).
    """
    if reserva.estado == 'cancelada':
        return 'Esta reserva fue cancelada', None
    if reserva.estado == 'confirmada':
        return 'Esta reserva ya está confirmada', None
    if reserva.estado == 'por_validar':
        return 'Ya enviaste un comprobante, el cajero lo está revisando', None

    archivo = request.files.get('comprobante')
    if archivo is None or not archivo.filename:
        return 'Selecciona la captura de tu pago', None
    contenido = archivo.read()
    if not contenido:
        return 'El archivo está vacío', None
    extension = extension_por_firma(contenido[:16])
    if extension is None:
        return 'Sube una imagen PNG, JPG o WEBP', None

    huella = hashlib.sha256(contenido).hexdigest()
    return None, (contenido, extension, huella)


def guardar_captura(prefijo, contenido, extension):
    """Guarda la captura con un nombre generado por nosotros (nunca se usa el
    nombre que envía el usuario) y devuelve ese nombre."""
    carpeta = current_app.config['UPLOAD_FOLDER']
    os.makedirs(carpeta, exist_ok=True)
    nombre = f'{prefijo}_{uuid.uuid4().hex}.{extension}'
    with open(os.path.join(carpeta, nombre), 'wb') as f:
        f.write(contenido)
    return nombre


def rechazar_comprobante(reserva, comprobante):
    """Body JSON: {"motivo": "..."}. Marca el comprobante como rechazado y la
    reserva vuelve a 'pendiente'. Devuelve un mensaje de error o None."""
    datos = request.get_json(silent=True) or {}
    motivo = (datos.get('motivo') or '').strip()
    if not motivo:
        return 'Indica el motivo del rechazo'

    comprobante.estado = 'rechazado'
    comprobante.motivo_rechazo = motivo[:200]
    comprobante.id_validador = session['id_usuario']
    comprobante.fecha_validacion = datetime.now()
    reserva.estado = 'pendiente'
    db.session.commit()
    return None
