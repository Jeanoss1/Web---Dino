"""Límite de intentos de inicio de sesión (contra fuerza bruta).
Es en memoria: sirve para un solo proceso; con varios procesos usar Redis."""
import time
from collections import defaultdict

from flask import current_app

_fallos = defaultdict(list)


def _limpiar(clave, ventana):
    ahora = time.time()
    _fallos[clave] = [t for t in _fallos[clave] if ahora - t < ventana]


def bloqueado(clave):
    cfg = current_app.config
    _limpiar(clave, cfg['VENTANA_INTENTOS_LOGIN'])
    return len(_fallos[clave]) >= cfg['LIMITE_INTENTOS_LOGIN']


def registrar_fallo(clave):
    _fallos[clave].append(time.time())


def limpiar(clave):
    _fallos.pop(clave, None)


def reiniciar_todo():
    _fallos.clear()
