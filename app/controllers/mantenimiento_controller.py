from app.tiempo import ahora

from flask import Blueprint, jsonify, request

from app.controllers.decoradores import rol_requerido
from app.database import db
from app.models.Flota import Flota
from app.models.Mantenimiento import Mantenimiento
from app.models.Repuesto import Repuesto


mantenimiento_bp = Blueprint(
    'mantenimiento',
    __name__
)

SOLO_ADMIN = ('administrador',)


def _mant_a_dict(m):
    return {
        'id_mantenimiento': m.id_mantenimiento,
        'id_flota': m.id_flota,
        'flota': m.flota.nombre,
        'tipo': m.tipo,
        'estado': m.estado,
        'fecha_inicio': (
            m.fecha_inicio.isoformat()
            if m.fecha_inicio
            else None
        ),
        'fecha_fin': (
            m.fecha_fin.isoformat()
            if m.fecha_fin
            else None
        ),
        'observacion': m.observacion,
        'repuesto': (
            m.repuesto.nombre
            if m.repuesto
            else None
        ),
    }


@mantenimiento_bp.route('/api/repuestos')
@rol_requerido(*SOLO_ADMIN)
def listar_repuestos():
    """
    ?bajo_stock=1 devuelve solo los que
    necesitan reposición.
    """

    repuestos = Repuesto.query.all()

    if request.args.get('bajo_stock'):
        repuestos = [
            r for r in repuestos
            if r.necesita_reposicion
        ]

    return jsonify([
        {
            'id_repuesto': r.id_repuesto,
            'nombre': r.nombre,
            'stock': r.stock,
            'stock_minimo': r.stock_minimo,
            'necesita_reposicion': (
                r.necesita_reposicion
            ),
        }
        for r in repuestos
    ])


@mantenimiento_bp.route(
    '/api/mantenimientos',
    methods=['POST']
)
@rol_requerido(*SOLO_ADMIN)
def registrar_mantenimiento():
    """
    Body JSON:

    {
        "id_flota": 1,
        "tipo": "preventivo",
        "observacion": "...",
        "id_repuesto": 2
    }

    La unidad pasa a estado 'mantenimiento' y,
    si se usa un repuesto, baja su stock.
    """

    datos = request.get_json(
        silent=True
    ) or {}

    flota = (
        db.session.get(
            Flota,
            datos['id_flota']
        )
        if datos.get('id_flota')
        else None
    )

    if flota is None:
        return jsonify(
            error='La unidad de flota no existe'
        ), 404

    if not datos.get('tipo'):
        return jsonify(
            error='Indica el tipo de mantenimiento'
        ), 400

    repuesto = None

    if datos.get('id_repuesto'):

        repuesto = db.session.get(
            Repuesto,
            datos['id_repuesto']
        )

        if repuesto is None:
            return jsonify(
                error='El repuesto no existe'
            ), 404

        if repuesto.stock <= 0:
            return jsonify(
                error=(
                    f'No hay stock de '
                    f'{repuesto.nombre}'
                )
            ), 400

        repuesto.stock -= 1

    mantenimiento = Mantenimiento(
        id_flota=flota.id_flota,
        tipo=datos['tipo'],
        observacion=datos.get('observacion'),
        fecha_inicio=ahora(),
        estado='en_proceso',
        repuesto=repuesto,
    )

    flota.estado = 'mantenimiento'

    db.session.add(mantenimiento)
    db.session.commit()

    return jsonify(
        _mant_a_dict(mantenimiento)
    ), 201


@mantenimiento_bp.route(
    '/api/mantenimientos/<int:id_mantenimiento>/finalizar',
    methods=['POST']
)
@rol_requerido(*SOLO_ADMIN)
def finalizar_mantenimiento(id_mantenimiento):

    mantenimiento = db.session.get(
        Mantenimiento,
        id_mantenimiento
    )

    if mantenimiento is None:
        return jsonify(
            error='Mantenimiento no encontrado'
        ), 404

    if mantenimiento.estado == 'finalizado':
        return jsonify(
            error='Este mantenimiento ya fue finalizado'
        ), 400

    mantenimiento.estado = 'finalizado'
    mantenimiento.fecha_fin = ahora()
    mantenimiento.flota.estado = 'disponible'
    # El conteo de uso para la próxima alerta preventiva empieza de nuevo
    mantenimiento.flota.contador_ultimo_mantenimiento = mantenimiento.flota.contador_actual

    db.session.commit()

    return jsonify(
        _mant_a_dict(mantenimiento)
    )


@mantenimiento_bp.route(
    '/api/flota/<int:id_flota>/mantenimientos'
)
@rol_requerido(*SOLO_ADMIN)
def historial_flota(id_flota):

    flota = db.session.get(
        Flota,
        id_flota
    )

    if flota is None:
        return jsonify(
            error='La unidad de flota no existe'
        ), 404

    return jsonify([
        _mant_a_dict(m)
        for m in flota.mantenimientos
    ])


# Se avisa desde el 90 % del límite para programar el mantenimiento a tiempo
UMBRAL_PROXIMO = 0.9


@mantenimiento_bp.route('/api/mantenimientos/alertas')
@rol_requerido(*SOLO_ADMIN)
def alertas_preventivas():
    """CA06.3: unidades que llegaron (o están por llegar) a su límite de uso
    desde el último mantenimiento: minutos en dinosaurios y ciclos en carros,
    motos y otros. No incluye las que ya están en mantenimiento."""
    alertas = []
    for u in Flota.query.filter(Flota.estado != 'mantenimiento').order_by(Flota.id_flota).all():
        uso, limite = u.uso_desde_mantenimiento, u.limite_uso_efectivo
        if uso < limite * UMBRAL_PROXIMO:
            continue
        alertas.append({
            'id_flota': u.id_flota,
            'unidad': u.nombre,
            'tipo': u.tipo,
            'sede': u.sucursal.nombre if u.sucursal else None,
            'uso': uso,
            'limite': limite,
            'unidad_medida': u.unidad_contador,
            'porcentaje': round(uso * 100 / limite, 1),
            'nivel': 'limite' if uso >= limite else 'proximo',
            'mensaje': (
                f'{u.nombre} llegó a su límite de uso ({uso} de {limite} {u.unidad_contador}): '
                'programa un mantenimiento preventivo'
                if uso >= limite else
                f'{u.nombre} está cerca de su límite de uso ({uso} de {limite} {u.unidad_contador})'
            ),
        })
    alertas.sort(key=lambda a: -a['porcentaje'])
    return jsonify(alertas)
