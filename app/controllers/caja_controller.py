from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request

from app.controllers.decoradores import rol_requerido
from app.database import db
from app.models.Caja import Caja
from app.models.MovimientoCaja import MovimientoCaja


caja_bp = Blueprint('caja', __name__)


ROLES_CAJA = ('administrador', 'cajero')


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
    }


def _caja_abierta():
    return Caja.query.filter_by(
        estado='abierta'
    ).first()


@caja_bp.route('/api/caja/abrir', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def abrir_caja():

    if _caja_abierta():
        return jsonify(
            error='Ya hay una caja abierta'
        ), 400

    datos = request.get_json(
        silent=True
    ) or {}

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

    caja = Caja(
        fecha_apertura=datetime.now(),
        monto_inicial=monto,
        estado='abierta'
    )

    db.session.add(caja)
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

    caja = _caja_abierta()

    if caja is None:
        return jsonify(
            error='Primero debes abrir la caja'
        ), 400

    datos = request.get_json(
        silent=True
    ) or {}

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

    caja = _caja_abierta()

    if caja is None:
        return jsonify(
            error='No hay una caja abierta'
        ), 400

    resumen = _caja_a_dict(caja)

    caja.monto_final = Decimal(
        str(resumen['saldo_actual'])
    )

    caja.fecha_cierre = datetime.now()
    caja.estado = 'cerrada'

    db.session.commit()

    return jsonify(
        _caja_a_dict(caja)
    )

