from datetime import datetime
from decimal import Decimal

from flask import current_app

from app.database import db
from app.models.Tarifa import Tarifa
from app.services import validadores as v
from app.services.errores import ErrorNegocio


def tarifa_vigente():
    tarifa = Tarifa.query.filter_by(activa=True).order_by(Tarifa.id_tarifa.desc()).first()
    if tarifa is None:
        raise ErrorNegocio('El administrador aún no configuró la tarifa.', 500)
    return tarifa


def calcular(bloques, tarifa=None):
    """minutos = bloques x minutos por bloque; total = bloques x precio por bloque."""
    tarifa = tarifa or tarifa_vigente()
    bloques = v.entero(bloques, 'bloques', 1, current_app.config['MAX_BLOQUES_VENTA'])
    return {
        'bloques': bloques,
        'minutos': bloques * tarifa.minutos,
        'precio_bloque': tarifa.precio,
        'total': tarifa.precio * bloques,
    }


def actualizar(precio, minutos, id_usuario):
    """Edita la tarifa estándar (solo el administrador)."""
    precio = v.dinero(precio, 'precio', Decimal('0.01'), Decimal('1000'), permitir_cero=False)
    minutos = v.entero(minutos, 'minutos por bloque', 1, 240)
    tarifa = Tarifa.query.filter_by(activa=True).first()
    if tarifa is None:
        tarifa = Tarifa(nombre='Estándar', activa=True)
        db.session.add(tarifa)
    tarifa.precio = precio
    tarifa.minutos = minutos
    tarifa.actualizado_en = datetime.now()
    tarifa.id_usuario = id_usuario
    db.session.commit()
    return tarifa
