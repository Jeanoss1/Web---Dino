"""Módulo de manejo centralizado de tiempo y zonas horarias para Dino Park.

Permite configurar la zona horaria operativa (por defecto 'America/Lima' / UTC-5)
evitando el desfasaje de 5 horas que ocurre en plataformas en la nube (Railway, Render, AWS)
cuyos servidores se ejecutan en UTC (UTC+0).

Proporciona funciones para generar marcas de tiempo consistentes y compatibles con
las columnas TIMESTAMP WITHOUT TIME ZONE existentes en PostgreSQL y SQLite.
"""
import os
from datetime import date, datetime, timedelta, timezone

# Zona horaria oficial de Perú (UTC-5, sin horario de verano)
ZONA_PERU = timezone(timedelta(hours=-5))
ZONA_UTC = timezone.utc


def obtener_zona_horaria():
    """Devuelve el objeto timezone configurado en APP_TIMEZONE (por defecto ZONA_PERU)."""
    tz_env = os.getenv('APP_TIMEZONE', 'America/Lima').upper().strip()
    if tz_env in ('UTC', 'Z', 'GMT'):
        return ZONA_UTC
    return ZONA_PERU


def ahora():
    """Devuelve la fecha y hora actual en la zona horaria del parque (Perú / UTC-5 por defecto),
    sin tzinfo (naive) para máxima compatibilidad con las columnas DateTime de la BD."""
    tz = obtener_zona_horaria()
    return datetime.now(tz).replace(tzinfo=None)


def ahora_aware():
    """Devuelve la fecha y hora actual con información explícita de timezone."""
    return datetime.now(obtener_zona_horaria())


def hoy():
    """Devuelve la fecha actual (date) en la zona horaria del parque."""
    return ahora().date()
