"""Lógica común de los comprobantes de pago (captura de Yape).

La usan comprobante_controller.py (reservas de flota) y entrada_controller.py
(reservas de entrada por tiempo): ambos flujos validan, guardan y rechazan
las capturas exactamente igual.

Soporta almacenamiento en la nube (Cloudinary, AWS S3, Cloudflare R2) con
respaldo automático en el disco local cuando no hay credenciales configuradas.
"""
import hashlib
import io
import os
import uuid
from datetime import datetime

from flask import current_app, jsonify, redirect, request, send_from_directory, session

from app.database import db
from app.tiempo import ahora

MIME_TYPES = {
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'webp': 'image/webp',
}


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


def _proveedor_almacenamiento():
    """Determina qué proveedor de almacenamiento usar según la configuración.

    Opciones: 's3' (cubre AWS S3 y Cloudflare R2), 'cloudinary', 'local'.
    """
    forzado = os.getenv('STORAGE_PROVIDER', '').lower().strip()
    if forzado in ('s3', 'r2', 'aws'):
        return 's3'
    if forzado == 'cloudinary':
        return 'cloudinary'
    if forzado == 'local':
        return 'local'

    if os.getenv('CLOUDINARY_URL') or os.getenv('CLOUDINARY_CLOUD_NAME'):
        return 'cloudinary'
    if os.getenv('S3_BUCKET_NAME'):
        return 's3'
    return 'local'


TIPOS_MIME = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'pdf': 'application/pdf'}


def _hay_bd():
    return 'sqlalchemy' in current_app.extensions


def _respaldar_en_bd(nombre, contenido, extension):
    """Copia la captura en la BD para que no se pierda si el disco del
    servidor se borra (Render). Se confirma junto con el comprobante."""
    if not _hay_bd():
        return
    from app.models.CapturaComprobante import CapturaComprobante
    db.session.add(CapturaComprobante(
        nombre=nombre,
        tipo_mime=TIPOS_MIME.get(extension.lower(), 'application/octet-stream'),
        datos=contenido,
    ))


def _captura_desde_bd(nombre):
    """Respuesta con la captura guardada en la BD, o None si no está."""
    if not _hay_bd():
        return None
    from flask import send_file
    from app.models.CapturaComprobante import CapturaComprobante
    copia = db.session.get(CapturaComprobante, nombre)
    if copia is None:
        return None
    return send_file(io.BytesIO(copia.datos), mimetype=copia.tipo_mime, download_name=nombre)


def _guardar_local(prefijo, contenido, extension):
    """Guarda la captura en el disco local dentro de UPLOAD_FOLDER y una copia en la BD."""
    carpeta = current_app.config['UPLOAD_FOLDER']
    os.makedirs(carpeta, exist_ok=True)
    nombre = f'{prefijo}_{uuid.uuid4().hex}.{extension}'
    with open(os.path.join(carpeta, nombre), 'wb') as f:
        f.write(contenido)
    _respaldar_en_bd(nombre, contenido, extension)
    return nombre


def _guardar_cloudinary(prefijo, contenido, extension):
    """Sube la captura a Cloudinary y devuelve la URL segura."""
    import cloudinary
    import cloudinary.uploader

    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    if cloud_name:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET'),
            secure=True,
        )

    public_id = f'{prefijo}_{uuid.uuid4().hex}'
    respuesta = cloudinary.uploader.upload(
        io.BytesIO(contenido),
        folder='comprobantes',
        public_id=public_id,
        resource_type='image',
        format=extension,
    )
    url = respuesta.get('secure_url') or respuesta.get('url')
    if url and len(url) <= 200:
        return url
    return respuesta.get('public_id') or f'comprobantes/{public_id}'


def _obtener_cliente_s3():
    """Crea y devuelve un cliente de S3 configurado para AWS S3 o Cloudflare R2."""
    import boto3
    from botocore.client import Config

    endpoint_url = os.getenv('S3_ENDPOINT_URL')
    access_key = os.getenv('AWS_ACCESS_KEY_ID') or os.getenv('S3_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY') or os.getenv('S3_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_REGION') or os.getenv('S3_REGION') or 'us-east-1'

    return boto3.client(
        's3',
        endpoint_url=endpoint_url or None,
        aws_access_key_id=access_key or None,
        aws_secret_access_key=secret_key or None,
        region_name=region,
        config=Config(signature_version='s3v4'),
    )


def _guardar_s3(prefijo, contenido, extension):
    """Sube la captura a AWS S3 o Cloudflare R2 y devuelve la clave o URL pública."""
    bucket = os.getenv('S3_BUCKET_NAME')
    key = f'comprobantes/{prefijo}_{uuid.uuid4().hex}.{extension}'
    content_type = MIME_TYPES.get(extension.lower(), 'application/octet-stream')

    cliente = _obtener_cliente_s3()
    cliente.put_object(
        Bucket=bucket,
        Key=key,
        Body=contenido,
        ContentType=content_type,
    )

    dominio_publico = os.getenv('S3_PUBLIC_DOMAIN')
    if dominio_publico:
        url_publica = f"{dominio_publico.rstrip('/')}/{key}"
        if len(url_publica) <= 200:
            return url_publica

    return key


def guardar_captura(prefijo, contenido, extension):
    """Guarda la captura en el servicio configurado (Cloudinary, AWS S3 / Cloudflare R2
    o disco local como fallback) y devuelve el identificador o URL a almacenar."""
    proveedor = _proveedor_almacenamiento()

    if proveedor == 'cloudinary':
        try:
            return _guardar_cloudinary(prefijo, contenido, extension)
        except Exception as e:
            current_app.logger.warning(
                f"Error al subir comprobante a Cloudinary: {e}. Usando respaldo local."
            )
            return _guardar_local(prefijo, contenido, extension)

    elif proveedor == 's3':
        try:
            return _guardar_s3(prefijo, contenido, extension)
        except Exception as e:
            current_app.logger.warning(
                f"Error al subir comprobante a S3/R2: {e}. Usando respaldo local."
            )
            return _guardar_local(prefijo, contenido, extension)

    return _guardar_local(prefijo, contenido, extension)


def servir_captura(archivo):
    """Genera la respuesta Flask para visualizar o descargar la captura del comprobante.

    - Si es una URL externa (Cloudinary, S3 con CDN público): redirige a la URL.
    - Si existe en el disco local: se sirve directamente con send_from_directory.
    - Si es un archivo de S3/Cloudflare R2: genera una URL prefirmada temporal (15 min) y redirige.
    - Si no existe: devuelve HTTP 404.
    """
    if not archivo:
        return jsonify(error='Comprobante no encontrado'), 404

    # 1. Redirección si ya es una URL completa (Cloudinary, S3 con dominio público)
    if archivo.startswith(('http://', 'https://')):
        return redirect(archivo)

    # 2. Si el archivo existe físicamente en el disco local (fallback o histórico)
    carpeta_local = current_app.config.get('UPLOAD_FOLDER')
    if carpeta_local and os.path.isfile(os.path.join(carpeta_local, archivo)):
        return send_from_directory(carpeta_local, archivo)

    # 2b. El disco se borró (redespliegue en Render): copia guardada en la BD
    desde_bd = _captura_desde_bd(archivo)
    if desde_bd is not None:
        return desde_bd

    # 3. AWS S3 o Cloudflare R2 (si hay bucket configurado o si el nombre inicia con 'comprobantes/' / 's3://')
    bucket = os.getenv('S3_BUCKET_NAME')
    if bucket or archivo.startswith(('comprobantes/', 's3://')):
        key = archivo
        if key.startswith('s3://'):
            partes = key[5:].split('/', 1)
            bucket = partes[0]
            key = partes[1] if len(partes) > 1 else ''

        if bucket:
            try:
                cliente = _obtener_cliente_s3()
                expiracion = int(os.getenv('S3_URL_EXPIRACION', 900))
                url = cliente.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket, 'Key': key},
                    ExpiresIn=expiracion,
                )
                return redirect(url)
            except Exception as e:
                current_app.logger.error(
                    f"Error al generar URL prefirmada de S3/R2 para '{archivo}': {e}"
                )
                return jsonify(error='No se pudo obtener el comprobante'), 500

    # 4. Cloudinary por public_id si no es URL
    if _proveedor_almacenamiento() == 'cloudinary':
        try:
            import cloudinary.utils
            url, _ = cloudinary.utils.cloudinary_url(archivo, secure=True)
            if url:
                return redirect(url)
        except Exception as e:
            current_app.logger.error(
                f"Error al resolver URL de Cloudinary para '{archivo}': {e}"
            )

    return jsonify(error='Comprobante no encontrado'), 404


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
    comprobante.fecha_validacion = ahora()
    reserva.estado = 'pendiente'
    db.session.commit()
    return None
