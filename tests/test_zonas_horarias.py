"""Pruebas unitarias para el manejo de zonas horarias y marcas de tiempo.

Verifica:
1. Configuración de zonas horarias (Perú UTC-5 por defecto, UTC configurable).
2. Generación de datetimes naive para compatibilidad con TIMESTAMP WITHOUT TIME ZONE.
3. Valores por defecto automáticos en modelos (Reserva, Venta, Pago, Ticket, etc.).
4. Compatibilidad en comparaciones de fechas (sin errores de naive vs aware).
5. Generación de códigos de tickets alineados a la fecha local del negocio.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from flask import Flask
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import db
from app.models.ComprobanteReserva import ComprobanteReserva
from app.models.LecturaFlota import LecturaFlota
from app.models.MovimientoCaja import MovimientoCaja
from app.models.Pago import Pago
from app.models.Reserva import Reserva
from app.models.ReservaEntrada import ReservaEntrada
from app.models.Ticket import Ticket
from app.models.Venta import Venta
from app.tiempo import ZONA_PERU, ZONA_UTC, ahora, ahora_aware, hoy, obtener_zona_horaria


def test_zona_horaria_por_defecto(monkeypatch):
    """Por defecto la zona horaria debe ser Perú (UTC-5)."""
    monkeypatch.delenv('APP_TIMEZONE', raising=False)
    tz = obtener_zona_horaria()
    assert tz == ZONA_PERU
    # Verificar offset de -5 horas (-18000 segundos)
    dt_peru = datetime.now(tz)
    assert dt_peru.utcoffset() == timedelta(hours=-5)


def test_zona_horaria_utc(monkeypatch):
    """Permite configurar APP_TIMEZONE=UTC explícitamente."""
    monkeypatch.setenv('APP_TIMEZONE', 'UTC')
    tz = obtener_zona_horaria()
    assert tz == ZONA_UTC
    dt_utc = datetime.now(tz)
    assert dt_utc.utcoffset() == timedelta(0)


def test_ahora_devuelve_naive_datetime():
    """ahora() debe devolver un datetime naive (sin tzinfo) para compatibilidad con la BD."""
    t = ahora()
    assert isinstance(t, datetime)
    assert t.tzinfo is None


def test_ahora_aware_devuelve_timezone():
    """ahora_aware() debe incluir la zona horaria correcta."""
    t = ahora_aware()
    assert isinstance(t, datetime)
    assert t.tzinfo is not None


def test_hoy_coincide_con_ahora_date():
    """hoy() devuelve exactamente la fecha actual en la zona horaria del parque."""
    assert hoy() == ahora().date()


def test_desfasaje_utc_vs_peru(monkeypatch):
    """Verifica que entre UTC y Perú existan exactamente 5 horas de diferencia."""
    monkeypatch.setenv('APP_TIMEZONE', 'America/Lima')
    t_peru = ahora()

    monkeypatch.setenv('APP_TIMEZONE', 'UTC')
    t_utc = ahora()

    # La diferencia entre UTC y Perú debe ser de ~5 horas (18000 segundos)
    diferencia_segundos = abs((t_utc - t_peru).total_seconds())
    assert 17990 <= diferencia_segundos <= 18010


def test_compatibilidad_comparaciones_fechas():
    """Verifica que fechas devueltas por ahora() se puedan comparar sin TypeError."""
    inicio = ahora()
    fin = inicio + timedelta(minutes=15)
    # Debe ser comparable directamente con datetimes sin zona horaria
    assert inicio < fin
    assert fin >= inicio


def test_modelos_default_tiempo():
    """Verifica que los modelos de SQLAlchemy usen ahora() como default al persistir."""
    app = Flask('test_time_models')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()

        # 1. Reserva
        r = Reserva(id_cliente=1, cantidad_personas=2, total=30.0)
        db.session.add(r)

        # 2. Venta
        v = Venta(id_usuario=1, total=50.0, estado='pendiente')
        db.session.add(v)

        # 3. Pago
        p = Pago(monto=50.0, metodo_pago='efectivo')
        db.session.add(p)

        # 4. Ticket
        tk = Ticket(codigo=f"T{ahora():%y%m%d}-TEST01")
        db.session.add(tk)

        # 5. ReservaEntrada
        re = ReservaEntrada(id_cliente=1, id_sucursal=1, total=25.0)
        db.session.add(re)

        db.session.commit()

        # Verificar que todos los campos DateTime se inicializaron automáticamente
        assert r.fecha_reserva is not None
        assert isinstance(r.fecha_reserva, datetime)
        assert r.fecha_reserva.date() == hoy()

        assert v.fecha is not None
        assert isinstance(v.fecha, datetime)
        assert v.fecha.date() == hoy()

        assert p.fecha_pago is not None
        assert isinstance(p.fecha_pago, datetime)
        assert p.fecha_pago.date() == hoy()

        assert tk.fecha_emision is not None
        assert isinstance(tk.fecha_emision, datetime)
        assert tk.fecha_emision.date() == hoy()

        assert re.fecha_reserva is not None
        assert isinstance(re.fecha_reserva, datetime)
        assert re.fecha_reserva.date() == hoy()
