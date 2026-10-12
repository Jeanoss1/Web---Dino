"""Los casos de app/pruebas/casos.py como pruebas de pytest (panel Testing de VS Code).

Usa el motor de app/pruebas/motor.py: BD aparte (dino_park_pruebas) que se
vacía al inicio y casos en el orden de la columna 'Orden' del Excel.

Los casos dependen de los anteriores (IDs, sesiones, reservas…), por eso se
preparan y ejecutan todos juntos: al lanzar uno solo desde VS Code se corren
también los anteriores y solo se informa el resultado del que elegiste.
"""
import shutil
import tempfile

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.database import db
from app.pruebas import motor

CASOS = motor.casos_ordenados()


@pytest.fixture(scope='session')
def resultados():
    """Prepara la BD de pruebas una sola vez y ejecuta todos los casos en orden."""
    carpeta = tempfile.mkdtemp(prefix='dino_pruebas_')
    app = None
    try:
        url = motor._url_bd_pruebas()
        try:
            motor._reiniciar_bd(url)
            app = motor._crear_app_pruebas(url, carpeta)
        except SQLAlchemyError as e:
            pytest.exit(f'No se pudo preparar la BD {url.database}: '
                        f'{getattr(e, "orig", None) or e}', returncode=1)

        ctx = motor.Contexto(app, carpeta)
        yield {c.id: motor._correr(c, ctx) for c in CASOS}
    finally:
        if app is not None:
            with app.app_context():
                db.engine.dispose()
        shutil.rmtree(carpeta, ignore_errors=True)


def _detalle(resultado):
    lineas = [f"{resultado['id']} – {resultado['nombre']}",
              f"Esperado: {resultado['esperado']}"]
    for v in resultado['verificaciones']:
        if not v['ok']:
            lineas.append(f"  ✘ {v['que']}: esperado {v['esperado']}, obtenido {v['obtenido']}")
    return '\n'.join(lineas)


@pytest.mark.parametrize('caso', CASOS, ids=[f'{c.id} {c.nombre}' for c in CASOS])
def test_caso(caso, resultados):
    resultado = resultados[caso.id]
    assert resultado['ok'], _detalle(resultado)
