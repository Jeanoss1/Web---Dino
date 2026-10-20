"""Motor de ejecución de los casos de prueba.

Cada ejecución:
1. Crea (si no existe) la BD dino_park_pruebas y la deja vacía.
2. Levanta una segunda instancia de la app apuntando a esa BD y carga el seed
   con el cajero de los casos (cajero@dinopark.pe / Cajero2026!).
3. Corre los casos en el orden de la columna 'Orden' del Excel y devuelve,
   por cada uno, ✔ si todas sus verificaciones pasan o ✘ si alguna falla.

La BD principal (DATABASE_URL) nunca se modifica.
"""
import json
import os
import shutil
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import date
from html import unescape
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.database import db

BD_PRUEBAS = 'dino_park_pruebas'

# Credenciales del cajero que usan los casos (hoja Instrucciones, paso 2)
CAJERO_PRUEBAS = {
    'CAJERO_CORREO': 'cajero@dinopark.pe',
    'CAJERO_CONTRASENA': 'Cajero2026!',
}

_candado = threading.Lock()


class ErrorPreparacion(Exception):
    """No se pudo dejar lista la BD de pruebas."""


class EjecucionEnCurso(Exception):
    """Otra persona ya está ejecutando las pruebas."""


# ------------------------------------------------------------ registro de casos
class Caso:
    def __init__(self, id_caso, orden, hu, nombre, esperado, funcion):
        self.id = id_caso
        self.orden = orden
        self.hu = hu
        self.nombre = nombre
        self.esperado = esperado
        self.funcion = funcion


CASOS = []


def caso(id_caso, orden, hu, nombre, esperado):
    """Decorador: registra una función como caso de prueba."""
    def registrar(funcion):
        CASOS.append(Caso(id_caso, orden, hu, nombre, esperado, funcion))
        return funcion
    return registrar


# ------------------------------------------------------------- verificaciones
def _texto(valor):
    if isinstance(valor, (dict, list, tuple)):
        return json.dumps(valor, ensure_ascii=False, default=str)
    if valor is None:
        return 'null'
    return str(valor)


class Revision:
    """Junta las verificaciones de un caso. El caso pasa si todas pasan."""

    def __init__(self):
        self.verificaciones = []

    def _agregar(self, que, esperado, obtenido, ok):
        self.verificaciones.append({
            'que': que,
            'esperado': esperado,
            'obtenido': obtenido,
            'ok': bool(ok),
        })
        return bool(ok)

    def ver(self, que, obtenido, esperado):
        """Compara un valor obtenido con el esperado."""
        return self._agregar(que, _texto(esperado), _texto(obtenido),
                             obtenido == esperado)

    def cumple(self, que, condicion, obtenido, esperado):
        """Verificación libre: `condicion` decide, los textos solo se muestran."""
        return self._agregar(que, _texto(esperado), _texto(obtenido), condicion)

    def falla(self, que, detalle):
        return self._agregar(que, '—', detalle, False)

    def http(self, resp, codigo, cuerpo=None):
        """Código HTTP y, si se indica, el JSON exacto de la respuesta."""
        ok = self.ver('HTTP', resp.status_code, codigo)
        if cuerpo is not None:
            ok = self.ver('Respuesta', resp.get_json(silent=True), cuerpo) and ok
        return ok

    def campos(self, que, datos, esperado):
        """Compara solo las claves de `esperado` dentro de `datos`."""
        obtenido = ({k: datos.get(k) for k in esperado}
                    if isinstance(datos, dict) else datos)
        return self.ver(que, obtenido, esperado)

    def redirige(self, resp, ruta):
        self.ver('HTTP', resp.status_code, 302)
        destino = urlparse(resp.headers.get('Location', '')).path or None
        return self.ver('Redirige a', destino, ruta)

    def mensaje(self, resp, texto):
        """El mensaje aparece en el HTML de la respuesta."""
        visible = texto in unescape(resp.get_data(as_text=True))
        return self.cumple(f'Mensaje "{texto}"', visible,
                           'mostrado' if visible else 'no aparece', 'mostrado')


# -------------------------------------------------------------------- contexto
class Contexto:
    """Lo que cada caso necesita: clientes HTTP con su sesión y acceso a la BD."""

    def __init__(self, app, carpeta):
        self.app = app
        self.carpeta = carpeta
        self.hoy = date.today()
        self._clientes = {}

    @property
    def fecha(self):
        return self.hoy.isoformat()

    @property
    def prefijo_ticket(self):
        return f'T{self.hoy:%y%m%d}-'

    def cliente(self, nombre):
        """Navegador con nombre (ana, carlos, cajero…) que conserva su sesión."""
        if nombre not in self._clientes:
            self._clientes[nombre] = self.app.test_client()
        return self._clientes[nombre]

    def nuevo_cliente(self):
        """Navegador nuevo, sin sesión (como una ventana de incógnito)."""
        return self.app.test_client()

    def login(self, cliente, identificador, contrasena, recordarme=False):
        datos = {'identificador': identificador, 'contrasena': contrasena}
        if recordarme:
            datos['recordarme'] = 'on'
        return cliente.post('/iniciar-sesion', data=datos)

    def api(self, cliente, url, cuerpo=None):
        """Igual que api() de la consola: GET sin cuerpo, POST JSON con cuerpo."""
        if cuerpo is None:
            return cliente.get(url)
        return cliente.post(url, json=cuerpo)

    def subir(self, cliente, id_reserva, contenido, nombre):
        from io import BytesIO
        return cliente.post(
            f'/api/reservas/{id_reserva}/comprobante',
            data={'comprobante': (BytesIO(contenido), nombre)},
            content_type='multipart/form-data',
        )

    def sql(self, consulta, **parametros):
        """Ejecuta SQL en la BD de pruebas (como en pgAdmin).
        Devuelve las filas, o la cantidad de filas afectadas."""
        with self.app.app_context():
            resultado = db.session.execute(text(consulta), parametros)
            salida = (resultado.fetchall() if resultado.returns_rows
                      else resultado.rowcount)
            db.session.commit()
            return salida

    def valor(self, consulta, **parametros):
        filas = self.sql(consulta, **parametros)
        return filas[0][0] if filas else None


# ------------------------------------------------------------- preparar la BD
def _url_bd_pruebas():
    principal = os.getenv('DATABASE_URL')
    propia = os.getenv('PRUEBAS_DATABASE_URL')
    if not principal and not propia:
        raise ErrorPreparacion('Falta DATABASE_URL en el archivo .env')

    url = make_url(propia) if propia else make_url(principal).set(database=BD_PRUEBAS)

    if principal and make_url(principal).database == url.database:
        raise ErrorPreparacion(
            'La BD de pruebas no puede ser la misma que la BD principal')
    return url


def _reiniciar_bd(url):
    """Crea la BD de pruebas si no existe y borra todas sus tablas."""
    admin = create_engine(url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    try:
        with admin.connect() as con:
            existe = con.execute(
                text('SELECT 1 FROM pg_database WHERE datname = :n'),
                {'n': url.database},
            ).scalar()
            if not existe:
                con.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()

    motor = create_engine(url, isolation_level='AUTOCOMMIT')
    try:
        with motor.connect() as con:
            con.execute(text('DROP SCHEMA IF EXISTS public CASCADE'))
            con.execute(text('CREATE SCHEMA public'))
    finally:
        motor.dispose()


@contextmanager
def _variables_de_entorno(**valores):
    anteriores = {k: os.environ.get(k) for k in valores}
    os.environ.update(valores)
    try:
        yield
    finally:
        for clave, valor in anteriores.items():
            if valor is None:
                os.environ.pop(clave, None)
            else:
                os.environ[clave] = valor


def _crear_app_pruebas(url, carpeta):
    from app import create_app
    from app.seed import cargar_datos_iniciales

    app = create_app({
        'SQLALCHEMY_DATABASE_URI': url.render_as_string(hide_password=False),
        'UPLOAD_FOLDER': carpeta,
        'TESTING': True,
        'SEMBRAR_DATOS': False,
        # Los casos reservan los turnos de 10:00 a 13:00 de hoy,
        # se ejecuten a la hora que se ejecuten
        'PERMITIR_TURNOS_PASADOS': True,
    })
    with app.app_context():
        db.create_all()
        with _variables_de_entorno(**CAJERO_PRUEBAS):
            cargar_datos_iniciales()
    return app


# ------------------------------------------------------------------- ejecutar
def _correr(caso_, ctx):
    revision = Revision()
    inicio = time.perf_counter()
    try:
        caso_.funcion(ctx, revision)
    except Exception as e:  # un caso roto no detiene a los demás
        revision.falla('Error al ejecutar', f'{type(e).__name__}: {e}')
    ok = bool(revision.verificaciones) and all(
        v['ok'] for v in revision.verificaciones)
    return {
        'id': caso_.id,
        'orden': caso_.orden,
        'hu': caso_.hu,
        'nombre': caso_.nombre,
        'esperado': caso_.esperado,
        'ok': ok,
        'verificaciones': revision.verificaciones,
        'ms': round((time.perf_counter() - inicio) * 1000),
    }


def casos_ordenados():
    from app.pruebas import casos  # noqa: F401  (registra los casos)
    return sorted(CASOS, key=lambda c: c.orden)


def ejecutar():
    """Ejecuta todos los casos y devuelve el resumen y los resultados."""
    if not _candado.acquire(blocking=False):
        raise EjecucionEnCurso('Las pruebas ya se están ejecutando, espera a que terminen')

    carpeta = tempfile.mkdtemp(prefix='dino_pruebas_')
    app = None
    inicio = time.perf_counter()
    try:
        url = _url_bd_pruebas()
        try:
            _reiniciar_bd(url)
            app = _crear_app_pruebas(url, carpeta)
        except SQLAlchemyError as e:
            raise ErrorPreparacion(
                f'No se pudo preparar la BD {url.database}: {getattr(e, "orig", None) or e}')

        ctx = Contexto(app, carpeta)
        resultados = [_correr(c, ctx) for c in casos_ordenados()]
    finally:
        if app is not None:
            with app.app_context():
                db.engine.dispose()
        shutil.rmtree(carpeta, ignore_errors=True)
        _candado.release()

    aprobados = sum(r['ok'] for r in resultados)
    return {
        'resumen': {
            'total': len(resultados),
            'aprobados': aprobados,
            'fallidos': len(resultados) - aprobados,
            'segundos': round(time.perf_counter() - inicio, 1),
            'fecha': date.today().isoformat(),
            'bd': url.database,
        },
        'resultados': resultados,
    }
