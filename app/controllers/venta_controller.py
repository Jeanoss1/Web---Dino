import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request, session

from app.controllers.decoradores import rol_requerido
from app.database import db

from app.models.Caja import Caja
from app.models.DetalleVenta import DetalleVenta
from app.models.MovimientoCaja import MovimientoCaja
from app.models.Pago import Pago
from app.models.Ticket import Ticket
from app.models.Venta import Venta


venta_bp = Blueprint('venta', __name__)


ROLES_CAJA = ('administrador', 'cajero')


def _venta_a_dict(v):
    return {
        'id_venta': v.id_venta,
        'fecha': (
            v.fecha.isoformat()
            if v.fecha
            else None
        ),
        'total': float(v.total or 0),
        'estado': v.estado,
        'detalles': [
            {
                'id_detalle_venta': d.id_detalle_venta,
                'precio': float(d.precio),
                'cantidad': d.cantidad,
                'subtotal': float(d.subtotal),
                'pagado': d.id_pago is not None,
            }
            for d in v.detalles
        ],
    }


@venta_bp.route('/api/ventas', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def crear_venta():
    """
    Body JSON:

    {
        "items": [
            {
                "precio": 15,
                "cantidad": 2
            }
        ]
    }
    """

    datos = request.get_json(
        silent=True
    ) or {}

    items = datos.get('items') or []

    if not items:
        return jsonify(
            error='La venta necesita al menos un item'
        ), 400

    venta = Venta(
        id_usuario=session['id_usuario'],
        estado='pendiente'
    )

    total = Decimal('0')

    try:
        for item in items:

            precio = Decimal(
                str(item.get('precio'))
            )

            cantidad = int(
                item.get('cantidad', 1)
            )

            if precio <= 0 or cantidad <= 0:
                raise ValueError

            detalle = DetalleVenta(
                precio=precio,
                cantidad=cantidad
            )

            detalle.calcular_subtotal()

            venta.detalles.append(detalle)

            total += detalle.subtotal

    except (
        InvalidOperation,
        ValueError,
        TypeError
    ):
        return jsonify(
            error=(
                'Cada item necesita un precio '
                'y una cantidad mayores a 0'
            )
        ), 400

    venta.total = total

    db.session.add(venta)
    db.session.commit()

    return jsonify(
        _venta_a_dict(venta)
    ), 201


@venta_bp.route('/api/ventas/<int:id_venta>')
@rol_requerido(*ROLES_CAJA)
def ver_venta(id_venta):

    venta = db.session.get(
        Venta,
        id_venta
    )

    if venta is None:
        return jsonify(
            error='Venta no encontrada'
        ), 404

    return jsonify(
        _venta_a_dict(venta)
    )


@venta_bp.route(
    '/api/ventas/<int:id_venta>/pago',
    methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def pagar_venta(id_venta):
    """
    Body JSON:

    {
        "metodo_pago": "efectivo"
    }

    Registra un pago y un ticket por cada
    detalle pendiente.

    Si es efectivo y hay caja abierta,
    también registra el ingreso en la caja.
    """

    datos = request.get_json(
        silent=True
    ) or {}

    metodo = (
        datos.get('metodo_pago') or ''
    ).strip()

    if not metodo:
        return jsonify(
            error='Indica el método de pago'
        ), 400

    venta = db.session.get(
        Venta,
        id_venta
    )

    if venta is None:
        return jsonify(
            error='Venta no encontrada'
        ), 404

    pendientes = [
        d
        for d in venta.detalles
        if d.id_pago is None
    ]

    if not pendientes:
        return jsonify(
            error='Esta venta ya está pagada'
        ), 400

    caja = Caja.query.filter_by(
        estado='abierta'
    ).first()

    tickets = []

    for detalle in pendientes:

        pago = Pago(
            monto=detalle.subtotal,
            metodo_pago=metodo,
            estado='pagado'
        )

        pago.detalle_venta = detalle

        pago.ticket = Ticket(
            codigo=(
                f"T{datetime.now():%y%m%d}-"
                f"{uuid.uuid4().hex[:6].upper()}"
            )
        )

        db.session.add(pago)
        db.session.flush()

        if (
            caja
            and metodo.lower() == 'efectivo'
        ):
            db.session.add(
                MovimientoCaja(
                    tipo='ingreso',
                    monto=detalle.subtotal,
                    descripcion=(
                        f'Venta {venta.id_venta}'
                    ),
                    id_caja=caja.id_caja,
                    ticket=pago.ticket,
                )
            )

        tickets.append(
            pago.ticket.codigo
        )

    venta.tipo_pago = metodo
    venta.estado = 'pagada'

    db.session.commit()

    return jsonify({
        **_venta_a_dict(venta),
        'tickets': tickets
    })
