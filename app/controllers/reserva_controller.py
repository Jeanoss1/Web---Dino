from datetime import datetime
from decimal import Decimal

from flask import Blueprint, jsonify, request, session, render_template

from app.controllers.decoradores import login_requerido
from app.database import db

from app.models.Cliente import Cliente
from app.models.DetalleReserva import DetalleReserva
from app.models.Flota import Flota
from app.models.Reserva import Reserva
from app.models.Turno import Turno


# ============================================================
# BLUEPRINT
# ============================================================

reserva_bp = Blueprint('reserva', __name__)


# ============================================================
# PÁGINA DE DISPONIBILIDAD
# ============================================================

@reserva_bp.route('/disponibilidad')
@login_requerido
def disponibilidad():
    return render_template('disponibilidad.html')


# ============================================================
# ERRORES DE NEGOCIO
# ============================================================

class ErrorNegocio(Exception):
    pass


# ============================================================
# CONVERTIR RESERVA A JSON
# ============================================================

def _reserva_a_dict(r):
    return {
        'id_reserva': r.id_reserva,

        'fecha_reserva': (
            r.fecha_reserva.isoformat()
            if r.fecha_reserva
            else None
        ),

        'estado': r.estado,

        'cantidad_personas': r.cantidad_personas,

        'total': float(r.total or 0),

        'detalles': [
            {
                'id_flota': d.id_flota,
                'flota': d.flota.nombre,
                'id_turno': d.id_turno
            }
            for d in r.detalles
        ],
    }


# ============================================================
# OBTENER CLIENTE ACTUAL
# ============================================================

def _cliente_actual():
    return Cliente.query.filter_by(
        correo=session.get('correo')
    ).first()


# ============================================================
# LISTAR TURNOS DISPONIBLES
# ============================================================

@reserva_bp.route('/api/turnos')
def listar_turnos():
    """
    Turnos disponibles.

    Filtros opcionales:

    ?fecha=AAAA-MM-DD
    ?id_flota=1
    """

    consulta = Turno.query.filter_by(
        estado='disponible'
    )

    # --------------------------------------------------------
    # FILTRO POR FLOTA
    # --------------------------------------------------------

    if request.args.get('id_flota'):
        consulta = consulta.filter_by(
            id_flota=request.args['id_flota']
        )

    # --------------------------------------------------------
    # FILTRO POR FECHA
    # --------------------------------------------------------

    if request.args.get('fecha'):

        try:
            dia = datetime.strptime(
                request.args['fecha'],
                '%Y-%m-%d'
            )

        except ValueError:
            return jsonify(
                error='La fecha debe tener el formato AAAA-MM-DD'
            ), 400

        consulta = consulta.filter(
            db.func.date(Turno.fecha) == dia.date()
        )

    # --------------------------------------------------------
    # RESPUESTA
    # --------------------------------------------------------

    return jsonify([
        {
            'id_turno': t.id_turno,
            'id_flota': t.id_flota,

            'horario_inicio': (
                t.horario_inicio.isoformat()
            ),

            'horario_fin': (
                t.horario_fin.isoformat()
            ),

            'capacidad': t.capacidad,
        }

        for t in consulta.order_by(
            Turno.horario_inicio
        ).all()
    ])


# ============================================================
# CREAR RESERVA
# ============================================================

@reserva_bp.route(
    '/api/reservas',
    methods=['POST']
)
@login_requerido
def crear_reserva():

    """
    Body JSON esperado:

    {
        "cantidad_personas": 2,
        "items": [
            {
                "id_flota": 1,
                "id_turno": 3
            }
        ]
    }
    """

    datos = request.get_json(
        silent=True
    ) or {}

    items = datos.get('items') or []

    # --------------------------------------------------------
    # VALIDAR ITEMS
    # --------------------------------------------------------

    if not items:
        return jsonify(
            error='Debes indicar al menos una atracción y un turno'
        ), 400

    # --------------------------------------------------------
    # BUSCAR CLIENTE
    # --------------------------------------------------------

    cliente = _cliente_actual()

    if cliente is None:
        return jsonify(
            error='Tu usuario no tiene un cliente asociado'
        ), 404

    try:

        # ----------------------------------------------------
        # CANTIDAD DE PERSONAS
        # ----------------------------------------------------

        cantidad_personas = int(
            datos.get(
                'cantidad_personas',
                1
            )
        )

        if cantidad_personas < 1:
            raise ErrorNegocio(
                'La cantidad de personas debe ser como mínimo 1'
            )

        # ----------------------------------------------------
        # CREAR RESERVA
        # ----------------------------------------------------

        reserva = Reserva(
            id_cliente=cliente.id_cliente,
            cantidad_personas=cantidad_personas,
            estado='pendiente',
        )

        db.session.add(reserva)

        total = Decimal('0')

        # ----------------------------------------------------
        # PROCESAR ATRACCIONES
        # ----------------------------------------------------

        for item in items:

            if (
                not item.get('id_flota')
                or not item.get('id_turno')
            ):
                raise ErrorNegocio(
                    'Cada item necesita id_flota e id_turno'
                )

            # -----------------------------------------------
            # BUSCAR FLOTA
            # -----------------------------------------------

            flota = db.session.get(
                Flota,
                item['id_flota']
            )

            # -----------------------------------------------
            # BUSCAR TURNO
            # -----------------------------------------------

            turno = db.session.get(
                Turno,
                item['id_turno']
            )

            if flota is None or turno is None:
                raise ErrorNegocio(
                    'La atracción o el turno no existe'
                )

            # -----------------------------------------------
            # VALIDAR RELACIÓN FLOTA / TURNO
            # -----------------------------------------------

            if turno.id_flota != flota.id_flota:
                raise ErrorNegocio(
                    'El turno no corresponde a esa atracción'
                )

            # -----------------------------------------------
            # VALIDAR DISPONIBILIDAD
            # -----------------------------------------------

            if (
                flota.estado != 'disponible'
                or turno.estado != 'disponible'
            ):
                raise ErrorNegocio(
                    f'{flota.nombre} no está disponible en ese turno'
                )

            # -----------------------------------------------
            # CREAR DETALLE
            # -----------------------------------------------

            detalle = DetalleReserva(
                id_flota=flota.id_flota,
                id_turno=turno.id_turno
            )

            reserva.detalles.append(
                detalle
            )

            db.session.flush()

            # -----------------------------------------------
            # CALCULAR CUPOS OCUPADOS
            # -----------------------------------------------

            ocupados = (
                DetalleReserva.query
                .join(Reserva)
                .filter(
                    DetalleReserva.id_turno
                    == turno.id_turno,

                    Reserva.estado
                    != 'cancelada'
                )
                .count()
            )

            # -----------------------------------------------
            # VALIDAR CAPACIDAD
            # -----------------------------------------------

            if ocupados > turno.capacidad:
                raise ErrorNegocio(
                    'El turno ya no tiene cupos'
                )

            # -----------------------------------------------
            # MARCAR TURNO COMO LLENO
            # -----------------------------------------------

            if ocupados == turno.capacidad:
                turno.estado = 'lleno'

            # -----------------------------------------------
            # SUMAR PRECIO
            # -----------------------------------------------

            total += Decimal(
                str(
                    flota.precio_hora or 0
                )
            )

        # ----------------------------------------------------
        # GUARDAR TOTAL
        # ----------------------------------------------------

        reserva.total = total

        db.session.commit()

    except (
        ErrorNegocio,
        ValueError
    ) as e:

        db.session.rollback()

        return jsonify(
            error=str(e)
        ), 400

    # --------------------------------------------------------
    # RESPUESTA EXITOSA
    # --------------------------------------------------------

    return jsonify(
        _reserva_a_dict(reserva)
    ), 201


# ============================================================
# MIS RESERVAS
# ============================================================

@reserva_bp.route('/api/reservas/mis')
@login_requerido
def mis_reservas():

    cliente = _cliente_actual()

    if cliente is None:
        return jsonify([])

    return jsonify([
        _reserva_a_dict(r)
        for r in cliente.reservas
    ])


# ============================================================
# VER UNA RESERVA
# ============================================================

@reserva_bp.route(
    '/api/reservas/<int:id_reserva>'
)
@login_requerido
def ver_reserva(id_reserva):

    reserva = db.session.get(
        Reserva,
        id_reserva
    )

    cliente = _cliente_actual()

    es_dueno = (
        cliente is not None
        and reserva is not None
        and reserva.id_cliente
        == cliente.id_cliente
    )

    es_personal = session.get('rol') in (
        'administrador',
        'cajero'
    )

    if (
        reserva is None
        or not (
            es_dueno
            or es_personal
        )
    ):
        return jsonify(
            error='Reserva no encontrada'
        ), 404

    return jsonify(
        _reserva_a_dict(reserva)
    )


# ============================================================
# CANCELAR RESERVA
# ============================================================

@reserva_bp.route(
    '/api/reservas/<int:id_reserva>/cancelar',
    methods=['POST']
)
@login_requerido
def cancelar_reserva(id_reserva):

    reserva = db.session.get(
        Reserva,
        id_reserva
    )

    cliente = _cliente_actual()

    es_dueno = (
        cliente is not None
        and reserva is not None
        and reserva.id_cliente
        == cliente.id_cliente
    )

    es_personal = session.get('rol') in (
        'administrador',
        'cajero'
    )

    if (
        reserva is None
        or not (
            es_dueno
            or es_personal
        )
    ):
        return jsonify(
            error='Reserva no encontrada'
        ), 404

    # --------------------------------------------------------
    # VALIDAR SI YA ESTÁ CANCELADA
    # --------------------------------------------------------

    if reserva.estado == 'cancelada':

        return jsonify(
            error='La reserva ya estaba cancelada'
        ), 400

    # --------------------------------------------------------
    # CANCELAR
    # --------------------------------------------------------

    reserva.estado = 'cancelada'

    # --------------------------------------------------------
    # LIBERAR TURNOS
    # --------------------------------------------------------

    for detalle in reserva.detalles:

        if detalle.turno.estado == 'lleno':

            detalle.turno.estado = 'disponible'

    # --------------------------------------------------------
    # GUARDAR
    # --------------------------------------------------------

    db.session.commit()

    return jsonify(
        _reserva_a_dict(reserva)
    )