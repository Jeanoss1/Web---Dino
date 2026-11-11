"""Pruebas unitarias y de integración para el almacenamiento de comprobantes en la nube.

Verifica:
1. Detección automática y forzada de proveedores (Cloudinary, S3/R2, Local).
2. Guardado y entrega local con compatibilidad histórica.
3. Integración con Cloudinary (subida y redirección a URL segura).
4. Integración con AWS S3 / Cloudflare R2 (subida, URL prefirmada y CDN público).
5. Resiliencia: Fallback a disco local en caso de fallo en la nube.
6. Respuestas HTTP 404 cuando el comprobante no existe.
"""
import io
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, make_response

from app.servicios_comprobante import (
    _guardar_local,
    _proveedor_almacenamiento,
    guardar_captura,
    servir_captura,
)

PNG_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
    b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00'
    b'\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
)


@pytest.fixture
def app_prueba():
    """Crea una aplicación Flask aislada con carpeta temporal de uploads."""
    carpeta_temp = tempfile.mkdtemp(prefix='dino_upload_test_')
    app = Flask('dino_test_storage')
    app.config['UPLOAD_FOLDER'] = carpeta_temp
    app.config['TESTING'] = True

    with app.app_context():
        yield app


def test_deteccion_proveedor_por_defecto(monkeypatch):
    """Sin variables de entorno en la nube, el proveedor por defecto es 'local'."""
    monkeypatch.delenv('STORAGE_PROVIDER', raising=False)
    monkeypatch.delenv('CLOUDINARY_URL', raising=False)
    monkeypatch.delenv('CLOUDINARY_CLOUD_NAME', raising=False)
    monkeypatch.delenv('S3_BUCKET_NAME', raising=False)

    assert _proveedor_almacenamiento() == 'local'


def test_deteccion_proveedor_forzado(monkeypatch):
    """STORAGE_PROVIDER tiene prioridad sobre las demás variables."""
    monkeypatch.setenv('STORAGE_PROVIDER', 'local')
    monkeypatch.setenv('CLOUDINARY_URL', 'cloudinary://1:2@test')
    monkeypatch.setenv('S3_BUCKET_NAME', 'mi-bucket')
    assert _proveedor_almacenamiento() == 'local'

    monkeypatch.setenv('STORAGE_PROVIDER', 's3')
    assert _proveedor_almacenamiento() == 's3'

    monkeypatch.setenv('STORAGE_PROVIDER', 'r2')
    assert _proveedor_almacenamiento() == 's3'

    monkeypatch.setenv('STORAGE_PROVIDER', 'cloudinary')
    assert _proveedor_almacenamiento() == 'cloudinary'


def test_deteccion_automatica(monkeypatch):
    """Detección automática si STORAGE_PROVIDER no está configurado."""
    monkeypatch.delenv('STORAGE_PROVIDER', raising=False)

    monkeypatch.setenv('CLOUDINARY_URL', 'cloudinary://1:2@test')
    monkeypatch.delenv('S3_BUCKET_NAME', raising=False)
    assert _proveedor_almacenamiento() == 'cloudinary'

    monkeypatch.delenv('CLOUDINARY_URL', raising=False)
    monkeypatch.setenv('S3_BUCKET_NAME', 'bucket-dino')
    assert _proveedor_almacenamiento() == 's3'


def test_almacenamiento_local_guardar_y_servir(app_prueba, monkeypatch):
    """Verifica que el almacenamiento local guarde en disco y servir_captura entregue el archivo."""
    monkeypatch.setenv('STORAGE_PROVIDER', 'local')

    nombre = guardar_captura('reserva1', PNG_BYTES, 'png')
    assert nombre.startswith('reserva1_')
    assert nombre.endswith('.png')
    assert len(nombre) <= 200

    ruta_archivo = os.path.join(app_prueba.config['UPLOAD_FOLDER'], nombre)
    assert os.path.isfile(ruta_archivo)
    with open(ruta_archivo, 'rb') as f:
        assert f.read() == PNG_BYTES

    # Servir captura
    with app_prueba.test_request_context():
        respuesta = servir_captura(nombre)
        assert respuesta.status_code == 200
        assert respuesta.direct_passthrough or respuesta.data == PNG_BYTES


def test_cloudinary_subida_y_redireccion(app_prueba, monkeypatch):
    """Simula la subida a Cloudinary y verifica que servir_captura redirija a la URL segura."""
    monkeypatch.setenv('STORAGE_PROVIDER', 'cloudinary')
    url_cloudinary = 'https://res.cloudinary.com/dinopark/image/upload/v12345/comprobantes/reserva5_abc.png'

    with patch('cloudinary.uploader.upload') as mock_upload:
        mock_upload.return_value = {
            'secure_url': url_cloudinary,
            'public_id': 'comprobantes/reserva5_abc',
        }
        resultado = guardar_captura('reserva5', PNG_BYTES, 'png')
        assert resultado == url_cloudinary
        assert len(resultado) <= 200

    # Al servir la captura guardada como URL, debe retornar un redirect HTTP 302
    with app_prueba.test_request_context():
        respuesta = servir_captura(url_cloudinary)
        assert respuesta.status_code == 302
        assert respuesta.headers['Location'] == url_cloudinary


def test_s3_subida_y_url_prefirmada(app_prueba, monkeypatch):
    """Simula AWS S3 / Cloudflare R2: subida con put_object y entrega con presigned URL."""
    monkeypatch.setenv('STORAGE_PROVIDER', 's3')
    monkeypatch.setenv('S3_BUCKET_NAME', 'dino-comprobantes')
    monkeypatch.delenv('S3_PUBLIC_DOMAIN', raising=False)

    mock_s3_client = MagicMock()
    url_prefirmada = 'https://dino-comprobantes.s3.amazonaws.com/comprobantes/reserva8_xyz.png?AWSAccessKeyId=123&Signature=abc'
    mock_s3_client.generate_presigned_url.return_value = url_prefirmada

    with patch('app.servicios_comprobante._obtener_cliente_s3', return_value=mock_s3_client):
        clave = guardar_captura('reserva8', PNG_BYTES, 'png')
        assert clave.startswith('comprobantes/reserva8_')
        assert clave.endswith('.png')
        assert len(clave) <= 200

        # Verificar que put_object fue llamado con los argumentos correctos
        mock_s3_client.put_object.assert_called_once()
        args_llamada = mock_s3_client.put_object.call_args[1]
        assert args_llamada['Bucket'] == 'dino-comprobantes'
        assert args_llamada['Key'] == clave
        assert args_llamada['Body'] == PNG_BYTES
        assert args_llamada['ContentType'] == 'image/png'

        # Al servir la captura, debe solicitar presigned URL y redirigir
        with app_prueba.test_request_context():
            respuesta = servir_captura(clave)
            assert respuesta.status_code == 302
            assert respuesta.headers['Location'] == url_prefirmada
            mock_s3_client.generate_presigned_url.assert_called_once_with(
                'get_object',
                Params={'Bucket': 'dino-comprobantes', 'Key': clave},
                ExpiresIn=900,
            )


def test_s3_con_dominio_publico_cdn(app_prueba, monkeypatch):
    """Cuando se define S3_PUBLIC_DOMAIN, guardar_captura devuelve la URL pública del CDN."""
    monkeypatch.setenv('STORAGE_PROVIDER', 's3')
    monkeypatch.setenv('S3_BUCKET_NAME', 'dino-comprobantes')
    monkeypatch.setenv('S3_PUBLIC_DOMAIN', 'https://cdn.dinopark.pe')

    mock_s3_client = MagicMock()
    with patch('app.servicios_comprobante._obtener_cliente_s3', return_value=mock_s3_client):
        url = guardar_captura('reserva9', PNG_BYTES, 'png')
        assert url.startswith('https://cdn.dinopark.pe/comprobantes/reserva9_')
        assert url.endswith('.png')
        assert len(url) <= 200

        with app_prueba.test_request_context():
            respuesta = servir_captura(url)
            assert respuesta.status_code == 302
            assert respuesta.headers['Location'] == url


def test_fallback_local_cuando_falla_nube(app_prueba, monkeypatch):
    """Si la subida a la nube falla por red o credenciales, se respalda automáticamente en local."""
    monkeypatch.setenv('STORAGE_PROVIDER', 's3')
    monkeypatch.setenv('S3_BUCKET_NAME', 'dino-comprobantes')

    mock_s3_client = MagicMock()
    mock_s3_client.put_object.side_effect = Exception("Conexión rechazada por AWS")

    with patch('app.servicios_comprobante._obtener_cliente_s3', return_value=mock_s3_client):
        nombre = guardar_captura('reserva_fallback', PNG_BYTES, 'png')
        # Guardado en local como respaldo
        assert nombre.startswith('reserva_fallback_')
        assert nombre.endswith('.png')
        ruta_archivo = os.path.join(app_prueba.config['UPLOAD_FOLDER'], nombre)
        assert os.path.isfile(ruta_archivo)

        # Y se puede servir localmente
        with app_prueba.test_request_context():
            resp = servir_captura(nombre)
            assert resp.status_code == 200


def test_servir_captura_inexistente(app_prueba, monkeypatch):
    """Si el archivo no existe en local ni en la nube, retorna 404."""
    monkeypatch.setenv('STORAGE_PROVIDER', 'local')
    with app_prueba.test_request_context():
        resp = make_response(servir_captura('archivo_que_no_existe.png'))
        assert resp.status_code == 404


def test_controlador_ver_comprobante_redireccion_cloud(monkeypatch):
    """Verifica que el controlador llame a servir_captura y redirija si el comprobante está en la nube."""
    from app.controllers.comprobante_controller import comprobante_bp

    app = Flask('test_app_controlador')
    app.secret_key = 'test-secret'
    app.config['UPLOAD_FOLDER'] = '/tmp/fake_uploads'
    app.config['TESTING'] = True
    app.register_blueprint(comprobante_bp)

    url_cloud = 'https://res.cloudinary.com/test/image/upload/v1/comprobantes/reserva1.png'
    mock_comprobante = MagicMock()
    mock_comprobante.archivo = url_cloud
    mock_comprobante.reserva.id_cliente = 10

    mock_cliente = MagicMock()
    mock_cliente.id_cliente = 10

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['id_usuario'] = 5
            sess['correo'] = 'cliente@test.com'
            sess['rol'] = 'cliente'

        with patch('app.controllers.comprobante_controller.db.session.get', return_value=mock_comprobante), \
             patch('app.controllers.comprobante_controller._cliente_actual', return_value=mock_cliente):
            resp = client.get('/comprobantes/1')
            assert resp.status_code == 302
            assert resp.headers['Location'] == url_cloud


def test_controlador_entrada_ver_comprobante_redireccion_cloud(monkeypatch):
    """Verifica ver_comprobante_entrada en el controlador de entradas con almacenamiento en la nube."""
    from app.controllers.entrada_controller import entrada_bp

    app = Flask('test_app_entrada')
    app.secret_key = 'test-secret'
    app.config['UPLOAD_FOLDER'] = '/tmp/fake_uploads'
    app.config['TESTING'] = True
    app.register_blueprint(entrada_bp)

    url_cloud = 'https://cdn.dinopark.pe/comprobantes/entrada5_abc.png'
    mock_comprobante = MagicMock()
    mock_comprobante.archivo = url_cloud
    mock_comprobante.reserva_entrada.id_cliente = 20

    mock_cliente = MagicMock()
    mock_cliente.id_cliente = 20

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['id_usuario'] = 8
            sess['correo'] = 'cliente2@test.com'
            sess['rol'] = 'cliente'

        with patch('app.controllers.entrada_controller.db.session.get', return_value=mock_comprobante), \
             patch('app.controllers.entrada_controller._cliente_actual', return_value=mock_cliente):
            resp = client.get('/comprobantes-entrada/5')
            assert resp.status_code == 302
            assert resp.headers['Location'] == url_cloud


