from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, session

from app.controllers.decoradores import rol_requerido
from app.database import db
from app.models.Caja import Caja
from app.models.Flota import Flota
from app.models.LecturaFlota import LecturaFlota
from app.models.MovimientoCaja import MovimientoCaja
from app.tiempo import ahora


caja_bp = Blueprint('caja', __name__)


ROLES_CAJA = ('administrador', 'cajero')


def _unidades_que_requieren_lectura(id_sucursal):
    """Toda la flota de la sede (sin importar su estado): el conteo físico
    hay que registrarlo igual aunque la unidad esté en mantenimiento."""
    if not id_sucursal:
        return []
    return Flota.query.filter_by(id_sucursal=id_sucursal).order_by(Flota.id_flota).all()


def _validar_lecturas(unidades, lecturas_enviadas):
    """Devuelve (mapa_id_flota->lectura_manual, error) revisando que venga
    una lectura numérica por cada unidad de la sede."""
    mapa = {}
    for item in lecturas_enviadas:
        try:
            mapa[int(item['id_flota'])] = int(item['lectura_manual'])
        except (KeyError, TypeError, ValueError):
            return None, 'Cada lectura debe indicar id_flota y lectura_manual (número entero)'

    faltantes = [u.nombre for u in unidades if u.id_flota not in mapa]
    if faltantes:
        return None, 'Falta registrar la lectura de: ' + ', '.join(faltantes)

    return mapa, None


def _cobros_por_metodo(c, ingresos_efectivo):
    """CA07.2: separa lo cobrado en efectivo (lo que entra a la caja física)
    de lo cobrado por Yape u otros medios en las ventas de la sede mientras
    la caja estuvo abierta. Los pagos digitales no suman al saldo de caja."""
    from app.models.Venta import Venta   # import local: evita ciclo de imports

    hasta = c.fecha_cierre or ahora()
    ventas = Venta.query.filter(
        Venta.id_sucursal == c.id_sucursal,
        Venta.estado == 'pagada',
        Venta.fecha >= c.fecha_apertura,
        Venta.fecha <= hasta,
    ).all()
    por_metodo = {'efectivo': float(ingresos_efectivo)}
    for v in ventas:
        metodo = (v.tipo_pago or 'efectivo').strip().lower()
        if metodo == 'efectivo':
            continue   # ya está en los movimientos de caja
        por_metodo[metodo] = round(por_metodo.get(metodo, 0) + float(v.total or 0), 2)
    return por_metodo


def _caja_a_dict(c):
    ingresos = sum(
        (
            m.monto
            for m in c.movimientos
            if m.tipo == 'ingreso'
        ),
        Decimal('0')
    )

    egresos = sum(
        (
            m.monto
            for m in c.movimientos
            if m.tipo == 'egreso'
        ),
        Decimal('0')
    )

    return {
        'id_caja': c.id_caja,
        'estado': c.estado,
        'id_usuario': c.id_usuario,
        'id_sucursal': c.id_sucursal,
        'fecha_apertura': c.fecha_apertura.isoformat(),
        'fecha_cierre': (
            c.fecha_cierre.isoformat()
            if c.fecha_cierre
            else None
        ),
        'monto_inicial': float(
            c.monto_inicial or 0
        ),
        'monto_final': (
            float(c.monto_final)
            if c.monto_final is not None
            else None
        ),
        'ingresos': float(ingresos),
        'egresos': float(egresos),
        'saldo_actual': float(
            (c.monto_inicial or 0)
            + ingresos
            - egresos
        ),
        'por_metodo': _cobros_por_metodo(c, ingresos),
    }


def _caja_abierta(id_sucursal=None, id_usuario=None):
    """Busca la caja abierta correspondiente al usuario y/o sede."""
    if id_usuario is None:
        id_usuario = session.get('id_usuario')
    if id_sucursal is None:
        if request:
            if request.is_json:
                datos = request.get_json(silent=True) or {}
                id_sucursal = datos.get('id_sucursal')
            if not id_sucursal:
                id_sucursal = request.args.get('id_sucursal')
        if not id_sucursal:
            id_sucursal = session.get('id_sucursal')

    # 1. Si el usuario actual tiene su propia caja abierta, esa es su caja activa
    if id_usuario:
        caja = Caja.query.filter_by(estado='abierta', id_usuario=id_usuario).first()
        if caja:
            return caja

    # 2. Si no, busca la caja abierta de la sucursal indicada
    if id_sucursal:
        caja = Caja.query.filter_by(estado='abierta', id_sucursal=id_sucursal).first()
        if caja:
            return caja

    # 3. Fallback cuando no hay usuario ni sede especificados
    if not id_usuario and not id_sucursal:
        return Caja.query.filter_by(estado='abierta').first()

    # Si es administrador y no tiene caja propia ni sede específica, consultar cualquier caja abierta
    if session.get('rol') == 'administrador':
        return Caja.query.filter_by(estado='abierta').first()

    return None


@caja_bp.route('/api/caja/abrir', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def abrir_caja():

    datos = request.get_json(
        silent=True
    ) or {}

    id_sucursal = datos.get('id_sucursal') or session.get('id_sucursal')
    id_usuario = session.get('id_usuario')

    if _caja_abierta(id_sucursal=id_sucursal, id_usuario=id_usuario):
        return jsonify(
            error='Ya hay una caja abierta'
        ), 400

    try:
        monto = Decimal(
            str(
                datos.get(
                    'monto_inicial',
                    0
                )
            )
        )

        if monto < 0:
            raise InvalidOperation

    except InvalidOperation:
        return jsonify(
            error='El monto inicial no es válido'
        ), 400

    unidades = _unidades_que_requieren_lectura(id_sucursal)

    mapa_lecturas = {}
    if unidades:
        mapa_lecturas, error = _validar_lecturas(unidades, datos.get('lecturas') or [])
        if error:
            return jsonify(error=f'No se puede abrir la caja: {error}'), 400

    caja = Caja(
        fecha_apertura=ahora(),
        monto_inicial=monto,
        estado='abierta',
        id_usuario=id_usuario,
        id_sucursal=id_sucursal,
    )

    db.session.add(caja)
    db.session.flush()

    for u in unidades:
        db.session.add(LecturaFlota(
            id_caja=caja.id_caja, id_flota=u.id_flota, momento='apertura',
            lectura_manual=mapa_lecturas[u.id_flota], contador_sistema=u.contador_actual,
        ))

    db.session.commit()

    return jsonify(
        _caja_a_dict(caja)
    ), 201


@caja_bp.route('/api/caja/actual')
@rol_requerido(*ROLES_CAJA)
def caja_actual():

    caja = _caja_abierta()

    if caja is None:
        return jsonify(
            error='No hay una caja abierta'
        ), 404

    return jsonify(
        _caja_a_dict(caja)
    )


@caja_bp.route(
    '/api/caja/movimientos',
    methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def registrar_movimiento():
    """
    Body JSON:

    {
        "tipo": "ingreso" | "egreso",
        "monto": 20,
        "descripcion": "..."
    }
    """

    datos = request.get_json(
        silent=True
    ) or {}

    caja = _caja_abierta(id_sucursal=datos.get('id_sucursal'))

    if caja is None:
        return jsonify(
            error='Primero debes abrir la caja'
        ), 400

    tipo = datos.get('tipo')

    if tipo not in (
        'ingreso',
        'egreso'
    ):
        return jsonify(
            error="El tipo debe ser 'ingreso' o 'egreso'"
        ), 400

    try:
        monto = Decimal(
            str(datos.get('monto'))
        )

        if monto <= 0:
            raise InvalidOperation

    except InvalidOperation:
        return jsonify(
            error='El monto debe ser mayor a 0'
        ), 400

    db.session.add(
        MovimientoCaja(
            tipo=tipo,
            monto=monto,
            descripcion=datos.get(
                'descripcion'
            ),
            id_caja=caja.id_caja,
        )
    )

    db.session.commit()

    return jsonify(
        _caja_a_dict(caja)
    ), 201


@caja_bp.route(
    '/api/caja/cerrar',
    methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def cerrar_caja():

    datos = request.get_json(silent=True) or {}
    caja = _caja_abierta(id_sucursal=datos.get('id_sucursal'))

    if caja is None:
        return jsonify(
            error='No hay una caja abierta'
        ), 400
    unidades = _unidades_que_requieren_lectura(caja.id_sucursal)

    if unidades:
        mapa_lecturas, error = _validar_lecturas(unidades, datos.get('lecturas') or [])
        if error:
            return jsonify(error=f'No se puede cerrar la caja: {error}'), 400

        for u in unidades:
            db.session.add(LecturaFlota(
                id_caja=caja.id_caja, id_flota=u.id_flota, momento='cierre',
                lectura_manual=mapa_lecturas[u.id_flota], contador_sistema=u.contador_actual,
            ))

    resumen = _caja_a_dict(caja)

    caja.monto_final = Decimal(
        str(resumen['saldo_actual'])
    )

    caja.fecha_cierre = ahora()
    caja.estado = 'cerrada'

    db.session.commit()

    return jsonify(
        _caja_a_dict(caja)
    )

