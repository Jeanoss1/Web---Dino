import io
import os
from datetime import date, timedelta

import pytest

os.environ['SEED_PASSWORD'] = 'Prueba2026!'

from app import create_app                      # noqa: E402
from app.config import PruebasConfig            # noqa: E402
from app.database import db                     # noqa: E402
from app.models import (Cajero, Flota, Sucursal, Usuario)  # noqa: E402
from app.seed import cargar_datos_iniciales     # noqa: E402
from app.services import franjas, seguridad     # noqa: E402

CLAVE = 'Prueba2026!'
PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 64


@pytest.fixture(autouse=True)
def hash_rapido(monkeypatch):
    """Solo en pruebas: un hash liviano para que los tests no tarden minutos."""
    from werkzeug.security import generate_password_hash as original
    rapido = lambda clave, *a, **k: original(clave, method='pbkdf2:sha256:1000')
    monkeypatch.setattr('app.seed.generate_password_hash', rapido)
    monkeypatch.setattr('app.services.usuarios.generate_password_hash', rapido)


@pytest.fixture()
def app(tmp_path):
    class Config(PruebasConfig):
        UPLOAD_FOLDER = str(tmp_path / 'subidas')

    app = create_app(Config)
    with app.app_context():
        db.create_all()
        cargar_datos_iniciales()
        seguridad.reiniciar_todo()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def iniciar_sesion(client, correo, clave=CLAVE):
    return client.post('/iniciar-sesion', data={'identificador': correo, 'contrasena': clave})


@pytest.fixture()
def como(app):
    """como('cajero1.realplaza@dinopark.pe') -> cliente HTTP con esa sesión iniciada."""
    def _como(correo):
        cliente = app.test_client()
        respuesta = iniciar_sesion(cliente, correo)
        assert respuesta.status_code == 302, 'no se pudo iniciar sesión'
        return cliente
    return _como


def usuario(correo):
    return Usuario.query.filter_by(correo=correo).first()


def sede(nombre):
    return Sucursal.query.filter_by(nombre=nombre).first()


def unidad(nombre_sede, indice=0):
    return (Flota.query.filter_by(id_sucursal=sede(nombre_sede).id_sucursal)
            .order_by(Flota.id_flota).all()[indice])


def franja_libre(id_flota, indice=0, dias=1):
    """Franja libre de la unidad (por defecto mañana, para que siempre sea futura)."""
    dia = date.today() + timedelta(days=dias)
    return franjas.listar_disponibles(id_flota, dia.isoformat())[indice]


def imagen(nombre='captura.png', contenido=PNG):
    return (io.BytesIO(contenido), nombre)


def vencer_todo(horas=2):
    """Simula que pasaron `horas`: adelanta los relojes de las cajas abiertas y de los alquileres
    en curso y finaliza los que vencieron (asi los datos quedan dentro de la ventana del turno)."""
    from app.database import db
    from app.models import Caja, RegistroUso
    from app.services import uso
    lapso = timedelta(hours=horas)
    for caja in Caja.query.filter_by(estado='abierta'):
        caja.fecha_apertura -= lapso + timedelta(hours=1)
    for u in RegistroUso.query.filter_by(estado='en_curso'):
        u.hora_inicio -= lapso
        u.hora_fin_prevista -= lapso
    db.session.commit()
    return uso.finalizar_vencidos()


def abrir_caja(client, monto=50, nombre_sede='Real Plaza', lecturas=None):
    """Abre la caja anotando la lectura de cada atraccion (por defecto, la del ultimo cierre)."""
    datos = {'monto_inicial': monto}
    for f in Flota.query.filter_by(id_sucursal=sede(nombre_sede).id_sucursal, estado='disponible'):
        datos[f'li_{f.id_flota}'] = f.lectura_manual if f.lectura_manual is not None else 0
    datos.update(lecturas or {})
    return client.post('/caja/abrir', data=datos)


def cerrar_caja(client, contado, nombre_sede='Real Plaza', finales=None, extra=None):
    """Cierra la caja; por defecto la lectura final = inicial (sin uso fisico)."""
    from app.models import LecturaCaja
    datos = {'monto_contado': contado}
    for l in LecturaCaja.query.join(Flota).filter(Flota.id_sucursal == sede(nombre_sede).id_sucursal,
                                                  LecturaCaja.lectura_final.is_(None)):
        datos[f'lf_{l.id_flota}'] = (finales or {}).get(l.id_flota, l.lectura_inicial)
    datos.update(extra or {})
    return client.post('/caja/cerrar', data=datos)


CAJERO_REAL = 'cajero1.realplaza@dinopark.pe'
CAJERO_REAL_MEDIO = 'cajero2.realplaza@dinopark.pe'
CAJERO_MEGA = 'cajero1.megaplaza@dinopark.pe'
ADMIN = 'admin@dinopark.pe'
CLIENTE1 = 'cliente1@ejemplo.pe'
CLIENTE2 = 'cliente2@ejemplo.pe'
