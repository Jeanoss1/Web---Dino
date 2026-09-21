"""Sedes, flota, repuestos y mantenimiento (gestión del administrador)."""
from datetime import datetime

from app.database import db
from app.models.Caja import Caja
from app.models.DetalleReserva import DetalleReserva
from app.models.Flota import CLASES_FLOTA, CONTADOR_POR_TIPO, TIPOS_CONTADOR, Flota
from app.models.Franja import Franja
from app.models.Mantenimiento import Mantenimiento
from app.models.Repuesto import Repuesto
from app.models.Sucursal import Sucursal
from app.services import validadores as v
from app.services.errores import ErrorNegocio

ESTADOS_FLOTA = ('disponible', 'mantenimiento', 'inactivo')


# ---------------------------------------------------------------------- sedes
def crear_sede(nombre, direccion, activa=True):
    nombre = v.texto(nombre, 'nombre')
    if Sucursal.query.filter(db.func.lower(Sucursal.nombre) == nombre.lower()).first():
        raise ErrorNegocio('Ya existe una sede con ese nombre.')
    sede = Sucursal(nombre=nombre, direccion=(direccion or '').strip()[:200],
                    estado='activa' if activa else 'inactiva')
    db.session.add(sede)
    db.session.commit()
    return sede


def alternar_sede(id_sucursal):
    sede = db.session.get(Sucursal, id_sucursal)
    if sede is None:
        raise ErrorNegocio('Sede no encontrada.', 404)
    if sede.estado == 'activa':
        if Caja.query.filter_by(id_sucursal=sede.id_sucursal, estado='abierta').count():
            raise ErrorNegocio('La sede tiene cajas abiertas; ciérralas antes de desactivarla.')
        sede.estado = 'inactiva'
    else:
        sede.estado = 'activa'
    db.session.commit()
    return sede


# ---------------------------------------------------------------------- flota
def crear_unidad(f):
    tipo = (f.get('tipo') or '').strip()
    clase = CLASES_FLOTA.get(tipo)
    if clase is None:
        raise ErrorNegocio('El tipo debe ser dinosaurio, carro, moto u otros.')
    sede = db.session.get(Sucursal, v.entero(f.get('id_sucursal'), 'sede', 1, 10**9))
    if sede is None:
        raise ErrorNegocio('La sede no existe.')
    extra = {'dinosaurio': 'especie', 'carro': 'velocidad', 'moto': 'cilindrada', 'otros': 'descripcion'}[tipo]
    contador = (f.get('tipo_contador') or '').strip() or CONTADOR_POR_TIPO[tipo]
    if contador not in TIPOS_CONTADOR:
        raise ErrorNegocio('El contador debe ser de minutos o de encendidos.')
    lectura = f.get('lectura_inicial')
    lectura = v.entero(lectura, 'lectura actual del contador', 0, 10**7) if str(lectura or '').strip() else None
    unidad = clase(
        tipo_contador=contador, lectura_manual=lectura,
        nombre=v.texto(f.get('nombre'), 'nombre'), modelo=(f.get('modelo') or '').strip()[:100],
        id_sucursal=sede.id_sucursal, estado='disponible', ciclos_uso=0,
        **{extra: (f.get('detalle') or '').strip()[:200]},
    )
    db.session.add(unidad)
    db.session.commit()
    return unidad


def cambiar_tipo_contador(id_flota, tipo_contador):
    """El administrador decide cómo se cuenta cada atracción (minutos o encendidos)."""
    unidad = db.session.get(Flota, id_flota)
    if unidad is None:
        raise ErrorNegocio('Unidad no encontrada.', 404)
    if tipo_contador not in TIPOS_CONTADOR:
        raise ErrorNegocio('El contador debe ser de minutos o de encendidos.')
    unidad.tipo_contador = tipo_contador
    db.session.commit()
    return unidad


def cambiar_estado_unidad(id_flota, estado):
    unidad = db.session.get(Flota, id_flota)
    if unidad is None:
        raise ErrorNegocio('Unidad no encontrada.', 404)
    if estado not in ESTADOS_FLOTA:
        raise ErrorNegocio('Estado no válido.')
    if estado != 'disponible' and reservas_futuras(id_flota):
        raise ErrorNegocio('La unidad tiene reservas activas; cancélalas o espera a que se cumplan.')
    unidad.estado = estado
    db.session.commit()
    return unidad


def reservas_futuras(id_flota):
    return (
        DetalleReserva.query.join(Franja, Franja.id_franja == DetalleReserva.id_franja)
        .filter(DetalleReserva.id_flota == id_flota, DetalleReserva.activo.is_(True),
                Franja.horario_fin >= datetime.now())
        .count()
    )


# ----------------------------------------------------------- mantenimiento
def crear_repuesto(nombre, stock, stock_minimo):
    repuesto = Repuesto(
        nombre=v.texto(nombre, 'nombre'), stock=v.entero(stock, 'stock', 0, 100000),
        stock_minimo=v.entero(stock_minimo, 'stock mínimo', 0, 100000), estado='activo',
    )
    db.session.add(repuesto)
    db.session.commit()
    return repuesto


def sumar_stock(id_repuesto, cantidad):
    repuesto = db.session.get(Repuesto, id_repuesto)
    if repuesto is None:
        raise ErrorNegocio('Repuesto no encontrado.', 404)
    repuesto.stock += v.entero(cantidad, 'cantidad', 1, 100000)
    db.session.commit()


def iniciar_mantenimiento(f):
    unidad = db.session.get(Flota, v.entero(f.get('id_flota'), 'unidad', 1, 10**9))
    if unidad is None:
        raise ErrorNegocio('La unidad no existe.', 404)
    tipo = v.texto(f.get('tipo'), 'tipo', 3, 50)
    if unidad.estado == 'mantenimiento':
        raise ErrorNegocio('La unidad ya está en mantenimiento.')
    if reservas_futuras(unidad.id_flota):
        raise ErrorNegocio('La unidad tiene reservas activas; cancélalas o espera a que se cumplan.')
    repuesto = None
    if f.get('id_repuesto'):
        repuesto = (db.session.query(Repuesto)
                    .filter_by(id_repuesto=v.entero(f['id_repuesto'], 'repuesto', 1, 10**9))
                    .with_for_update().first())
        if repuesto is None:
            raise ErrorNegocio('El repuesto no existe.', 404)
        if repuesto.stock <= 0:
            raise ErrorNegocio(f'No hay stock de {repuesto.nombre}.')
        repuesto.stock -= 1
    mant = Mantenimiento(
        id_flota=unidad.id_flota, tipo=tipo, observacion=(f.get('observacion') or '').strip()[:300],
        fecha_inicio=datetime.now(), estado='en_proceso', repuesto=repuesto,
    )
    unidad.estado = 'mantenimiento'
    db.session.add(mant)
    db.session.commit()
    return mant


def finalizar_mantenimiento(id_mantenimiento):
    mant = db.session.get(Mantenimiento, id_mantenimiento)
    if mant is None:
        raise ErrorNegocio('Mantenimiento no encontrado.', 404)
    if mant.estado == 'finalizado':
        raise ErrorNegocio('Este mantenimiento ya fue finalizado.')
    mant.estado = 'finalizado'
    mant.fecha_fin = datetime.now()
    mant.flota.estado = 'disponible'
    db.session.commit()
