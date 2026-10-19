"""Alquiler de flota en caja (Real Plaza / Mega Plaza): el cajero elige una
unidad disponible, cobra un precio fijo por un tiempo fijo (ej. S/10 por 12
min) y la unidad vuelve a estar disponible cuando el cajero marca
"Finalizar alquiler". Reusa el mismo pipeline de Venta/DetalleVenta/Pago/
Ticket que ya existe (venta_controller.py NO se toca), igual patrón que
entrada_controller.py para Hoyos Rubio.

No confundir con reserva_controller.py: eso es la reserva ONLINE por turno
fijo de 20 min (con comprobante Yape); esto es la venta EN CAJA por tiempo
fijo de 12 min, pagada al instante."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from flask import Blueprint, jsonify, render_template, request, session

from app.controllers.decoradores import rol_requerido
from app.controllers.venta_controller import _venta_a_dict
from app.database import db

from app.models.Caja import Caja
from app.models.DetalleVenta import DetalleVenta
from app.models.Flota import Flota
from app.models.LecturaFlota import LecturaFlota
from app.models.Sucursal import Sucursal
from app.models.Venta import Venta


flota_bp = Blueprint('flota_alquiler', __name__)

ROLES_CAJA = ('administrador', 'cajero')

CONTADOR_POR_TIPO = {
    'dinosaurio': 'contador_minutos',
    'carro': 'ciclos_uso',
    'moto': 'ciclos_uso',
    'otros': 'ciclos_uso',
}


def _contador_actual(unidad):
    return unidad.contador_actual


# ============================================================
# PÁGINA
# ============================================================

@flota_bp.route('/caja/flota')
@rol_requerido(*ROLES_CAJA)
def pagina_caja_flota():
    return render_template('caja_flota.html')


# ============================================================
# CATÁLOGO
# ============================================================

@flota_bp.route('/api/sedes/con-flota')
@rol_requerido(*ROLES_CAJA)
def listar_sedes_con_flota():
    ids = {f.id_sucursal for f in Flota.query.all()}
    sedes = Sucursal.query.filter(Sucursal.id_sucursal.in_(ids)).order_by(Sucursal.nombre).all()
    return jsonify([
        {'id_sucursal': s.id_sucursal, 'nombre': s.nombre, 'direccion': s.direccion}
        for s in sedes
    ])


@flota_bp.route('/api/flota/unidades')
@rol_requerido(*ROLES_CAJA)
def listar_unidades_de_sede():
    """Todas las unidades de la sede (sin importar su estado): la usa el
    formulario de lecturas manuales al abrir/cerrar caja."""
    id_sucursal = request.args.get('id_sucursal', type=int)
    if not id_sucursal:
        return jsonify(error='Indica id_sucursal'), 400

    unidades = Flota.query.filter_by(id_sucursal=id_sucursal).order_by(Flota.id_flota).all()
    return jsonify([
        {
            'id_flota': u.id_flota,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'estado': u.estado,
            'contador_actual': u.contador_actual,
        }
        for u in unidades
    ])


@flota_bp.route('/api/flota/alquilable')
@rol_requerido(*ROLES_CAJA)
def listar_flota_alquilable():
    id_sucursal = request.args.get('id_sucursal', type=int)
    if not id_sucursal:
        return jsonify(error='Indica id_sucursal'), 400

    unidades = Flota.query.filter_by(id_sucursal=id_sucursal, estado='disponible').all()
    return jsonify([
        {
            'id_flota': u.id_flota,
            'nombre': u.nombre,
            'tipo': u.tipo,
            'precio_alquiler': float(u.precio_alquiler or 0),
            'duracion_alquiler_minutos': u.duracion_alquiler_minutos or 12,
        }
        for u in unidades
    ])


# ============================================================
# VENTA / ALQUILER EN CAJA
# ============================================================

@flota_bp.route('/api/ventas/alquiler', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def crear_venta_alquiler():
    """
    Body JSON: {"id_flota": 3}

    Crea la venta con el precio fijo de la unidad, marca la unidad como
    'alquilado' y arranca el temporizador. El cobro se hace después con el
    ya existente POST /api/ventas/<id>/pago (venta_controller.py).
    """
    datos = request.get_json(silent=True) or {}
    id_flota = datos.get('id_flota')
    if not id_flota:
        return jsonify(error='Indica id_flota'), 400

    unidad = db.session.get(Flota, id_flota)
    if unidad is None:
        return jsonify(error='La unidad no existe'), 404
    if unidad.estado != 'disponible':
        return jsonify(error=f'{unidad.nombre} no está disponible'), 400
    if not unidad.precio_alquiler:
        return jsonify(error=f'{unidad.nombre} no tiene configurado un precio de alquiler'), 400

    ahora = datetime.now()
    venta = Venta(id_usuario=session['id_usuario'], id_sucursal=unidad.id_sucursal, estado='pendiente')
    detalle = DetalleVenta(
        precio=unidad.precio_alquiler, cantidad=1,
        id_flota=unidad.id_flota, hora_inicio=ahora,
    )
    detalle.calcular_subtotal()
    venta.detalles.append(detalle)
    venta.total = detalle.subtotal

    unidad.estado = 'alquilado'

    db.session.add(venta)
    db.session.commit()

    return jsonify(_venta_a_dict(venta)), 201


# ============================================================
# TEMPORIZADOR: ALQUILERES ACTIVOS
# ============================================================

def _alquiler_activo_a_dict(d):
    return {
        'id': d.id_detalle_venta,
        'id_flota': d.id_flota,
        'unidad': d.flota.nombre,
        'tipo': d.flota.tipo,
        'duracion_minutos': d.flota.duracion_alquiler_minutos or 12,
        'hora_inicio': d.hora_inicio.isoformat(),
    }


@flota_bp.route('/api/caja/alquileres-activos')
@rol_requerido(*ROLES_CAJA)
def listar_alquileres_activos():
    limite = datetime.now() - timedelta(hours=6)

    detalles = (
        DetalleVenta.query
        .join(Venta)
        .filter(
            DetalleVenta.id_flota.isnot(None),
            DetalleVenta.hora_inicio.isnot(None),
            DetalleVenta.hora_inicio >= limite,
            DetalleVenta.hora_fin.is_(None),
            Venta.estado == 'pagada',
        )
        .all()
    )

    activos = [_alquiler_activo_a_dict(d) for d in detalles]
    activos.sort(key=lambda a: a['hora_inicio'])
    return jsonify(activos)


@flota_bp.route('/api/caja/alquileres-activos/<int:id_detalle>/finalizar', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def finalizar_alquiler(id_detalle):
    detalle = db.session.get(DetalleVenta, id_detalle)
    if detalle is None or detalle.id_flota is None:
        return jsonify(error='Alquiler no encontrado'), 404
    if detalle.hora_fin is not None:
        return jsonify(error='Este alquiler ya fue finalizado'), 400

    unidad = detalle.flota
    detalle.hora_fin = datetime.now()
    unidad.estado = 'disponible'

    campo = CONTADOR_POR_TIPO.get(unidad.tipo, 'ciclos_uso')
    incremento = (unidad.duracion_alquiler_minutos or 12) if campo == 'contador_minutos' else 1
    setattr(unidad, campo, (getattr(unidad, campo) or 0) + incremento)

    db.session.commit()
    return jsonify(ok=True, contador=_contador_actual(unidad))


# ============================================================
# LECTURAS MANUALES DE CAJA (contador físico vs. contador del sistema)
# ============================================================

def _lectura_a_dict(l):
    return {
        'id_lectura': l.id_lectura,
        'id_flota': l.id_flota,
        'unidad': l.flota.nombre,
        'momento': l.momento,
        'lectura_manual': l.lectura_manual,
        'contador_sistema': l.contador_sistema,
        'diferencia': l.diferencia,
        'fecha': l.fecha.isoformat(),
    }


@flota_bp.route('/api/caja/lecturas', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def registrar_lectura():
    """Body: {"id_caja": 1, "momento": "apertura", "lecturas": [{"id_flota": 3, "lectura_manual": 120}]}"""
    datos = request.get_json(silent=True) or {}
    id_caja = datos.get('id_caja')
    momento = datos.get('momento')
    lecturas = datos.get('lecturas') or []

    if momento not in ('apertura', 'cierre'):
        return jsonify(error="momento debe ser 'apertura' o 'cierre'"), 400
    if db.session.get(Caja, id_caja) is None:
        return jsonify(error='Caja no encontrada'), 404
    if not lecturas:
        return jsonify(error='Indica al menos una lectura'), 400

    creadas = []
    for item in lecturas:
        unidad = db.session.get(Flota, item.get('id_flota'))
        if unidad is None:
            return jsonify(error=f"La unidad {item.get('id_flota')} no existe"), 404
        try:
            lectura_manual = int(item['lectura_manual'])
        except (KeyError, ValueError, TypeError):
            return jsonify(error='lectura_manual debe ser un número entero'), 400

        lectura = LecturaFlota(
            id_caja=id_caja, id_flota=unidad.id_flota, momento=momento,
            lectura_manual=lectura_manual, contador_sistema=_contador_actual(unidad),
        )
        db.session.add(lectura)
        creadas.append(lectura)

    db.session.commit()
    return jsonify([_lectura_a_dict(l) for l in creadas]), 201


@flota_bp.route('/api/caja/lecturas')
@rol_requerido(*ROLES_CAJA)
def listar_lecturas():
    id_caja = request.args.get('id_caja', type=int)
    if not id_caja:
        return jsonify(error='Indica id_caja'), 400
    lecturas = LecturaFlota.query.filter_by(id_caja=id_caja).order_by(LecturaFlota.id_lectura).all()
    return jsonify([_lectura_a_dict(l) for l in lecturas])
