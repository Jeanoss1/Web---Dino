from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, session

from app.controllers.decoradores import rol_requerido
from app.database import db
from app.models.Caja import Caja
from app.models.Flota import Flota
from app.models.LecturaFlota import LecturaFlota
from app.models.MovimientoCaja import MovimientoCaja


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

    id_sucursal = datos.get('id_sucursal') or session.get('id_sucursal')
    unidades = _unidades_que_requieren_lectura(id_sucursal)

    mapa_lecturas = {}
    if unidades:
        mapa_lecturas, error = _validar_lecturas(unidades, datos.get('lecturas') or [])
        if error:
            return jsonify(error=f'No se puede abrir la caja: {error}'), 400

    caja = Caja(
        fecha_apertura=datetime.now(),
        monto_inicial=monto,
        estado='abierta',
        id_usuario=session.get('id_usuario'),
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

    datos = request.get_json(silent=True) or {}
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

    caja.fecha_cierre = datetime.now()
    caja.estado = 'cerrada'

    db.session.commit()

    return jsonify(
        _caja_a_dict(caja)
    )

