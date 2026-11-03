from datetime import datetime

from flask import (Blueprint, current_app, jsonify, render_template, request,
                   send_from_directory, session)

from sqlalchemy.orm import joinedload, selectinload

from app.controllers.decoradores import login_requerido, rol_requerido
from app.database import db
from app.models.Cliente import Cliente
from app.models.ComprobanteReserva import ComprobanteReserva
from app.models.DetalleReserva import DetalleReserva
from app.models.Reserva import Reserva
from app.servicios_comprobante import (guardar_captura, rechazar_comprobante,
                                         validar_captura)

comprobante_bp = Blueprint('comprobante', __name__)

ROLES_CAJA = ('administrador', 'cajero')


def _con_relaciones(consulta, con_cliente=False):
    """Trae detalles, unidades, turnos y comprobantes en 3-4 consultas en
    lugar de 3-4 consultas por cada reserva de la lista."""
    detalles = selectinload(Reserva.detalles)
    opciones = [
        detalles.joinedload(DetalleReserva.flota),
        detalles.joinedload(DetalleReserva.turno),
        selectinload(Reserva.comprobantes),
    ]
    if con_cliente:
        opciones.append(joinedload(Reserva.cliente))
    return consulta.options(*opciones)


# ----------------------------------------------------------------- utilidades
def _cliente_actual():
    return Cliente.query.filter_by(correo=session.get('correo')).first()


def _es_personal():
    return session.get('rol') in ROLES_CAJA


def _detalles(reserva):
    return [
        {
            'unidad': d.flota.nombre,
            'inicio': d.turno.horario_inicio.isoformat(),
            'fin': d.turno.horario_fin.isoformat(),
        }
        for d in reserva.detalles
    ]


def _comprobante_a_dict(c):
    return {
        'id_comprobante': c.id_comprobante,
        'estado': c.estado,
        'monto': float(c.monto),
        'fecha_subida': c.fecha_subida.isoformat(),
        'motivo_rechazo': c.motivo_rechazo,
        'url': f'/comprobantes/{c.id_comprobante}',
    }


def _reserva_a_dict(r, con_cliente=False):
    ultimo = r.comprobantes[-1] if r.comprobantes else None
    datos = {
        'id_reserva': r.id_reserva,
        'fecha_reserva': r.fecha_reserva.isoformat() if r.fecha_reserva else None,
        'estado': r.estado,
        'cantidad_personas': r.cantidad_personas,
        'total': float(r.total or 0),
        'detalles': _detalles(r),
        'comprobante': _comprobante_a_dict(ultimo) if ultimo else None,
    }
    if con_cliente:
        datos['cliente'] = {
            'nombre': f'{r.cliente.nombre} {r.cliente.apellido}',
            'dni': r.cliente.dni,
            'telefono': r.cliente.telefono,
        }
    return datos


# ------------------------------------------------------------------- páginas
@comprobante_bp.route('/mis-reservas')
@login_requerido
def pagina_mis_reservas():
    return render_template('mis_reservas.html')


@comprobante_bp.route('/caja/validaciones')
@rol_requerido(*ROLES_CAJA)
def pagina_validaciones():
    return render_template('validar_reservas.html')


# ----------------------------------------------------------- lado del cliente
@comprobante_bp.route('/api/mis-reservas')
@login_requerido
def mis_reservas():
    cliente = _cliente_actual()
    if cliente is None:
        return jsonify([])
    reservas = (
        _con_relaciones(Reserva.query.filter_by(id_cliente=cliente.id_cliente))
        .order_by(Reserva.id_reserva.desc())
        .all()
    )
    return jsonify([_reserva_a_dict(r) for r in reservas])


@comprobante_bp.route('/api/reservas/<int:id_reserva>/comprobante', methods=['POST'])
@login_requerido
def subir_comprobante(id_reserva):
    """Recibe la captura del pago (multipart/form-data, campo 'comprobante')."""
    reserva = db.session.get(Reserva, id_reserva)
    cliente = _cliente_actual()
    if reserva is None or cliente is None or reserva.id_cliente != cliente.id_cliente:
        return jsonify(error='Reserva no encontrada'), 404
    error, captura = validar_captura(reserva)
    if error:
        return jsonify(error=error), 400
    contenido, extension, huella = captura

    repetido = (
        ComprobanteReserva.query
        .filter(ComprobanteReserva.hash_archivo == huella,
                ComprobanteReserva.id_reserva != reserva.id_reserva,
                ComprobanteReserva.estado.in_(['por_validar', 'aceptado']))
        .first()
    )
    if repetido:
        return jsonify(error='Esta captura ya fue usada en otra reserva'), 400

    nombre = guardar_captura(f'reserva{reserva.id_reserva}', contenido, extension)

    comprobante = ComprobanteReserva(
        id_reserva=reserva.id_reserva, metodo_pago='yape',
        monto=reserva.total, archivo=nombre, hash_archivo=huella,
        estado='por_validar',
    )
    reserva.estado = 'por_validar'
    db.session.add(comprobante)
    db.session.commit()
    return jsonify(_reserva_a_dict(reserva)), 201


@comprobante_bp.route('/comprobantes/<int:id_comprobante>')
@login_requerido
def ver_comprobante(id_comprobante):
    """Solo lo ve el dueño de la reserva o el personal de caja."""
    comprobante = db.session.get(ComprobanteReserva, id_comprobante)
    if comprobante is None:
        return jsonify(error='Comprobante no encontrado'), 404
    cliente = _cliente_actual()
    es_dueno = cliente is not None and comprobante.reserva.id_cliente == cliente.id_cliente
    if not (es_dueno or _es_personal()):
        return jsonify(error='Comprobante no encontrado'), 404
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], comprobante.archivo)


# ------------------------------------------------------------ lado del cajero
@comprobante_bp.route('/api/caja/reservas')
@rol_requerido(*ROLES_CAJA)
def listar_reservas_caja():
    """?estado=por_validar (por defecto) | confirmada"""
    estado = request.args.get('estado', 'por_validar')
    if estado not in ('por_validar', 'confirmada'):
        return jsonify(error="El estado debe ser 'por_validar' o 'confirmada'"), 400
    orden = Reserva.id_reserva.asc() if estado == 'por_validar' else Reserva.id_reserva.desc()
    reservas = (
        _con_relaciones(Reserva.query.filter_by(estado=estado), con_cliente=True)
        .order_by(orden).limit(100).all()
    )
    return jsonify([_reserva_a_dict(r, con_cliente=True) for r in reservas])


def _comprobante_por_validar(reserva):
    if reserva is None or reserva.estado != 'por_validar':
        return None
    for c in reversed(reserva.comprobantes):
        if c.estado == 'por_validar':
            return c
    return None


@comprobante_bp.route('/api/reservas/<int:id_reserva>/aceptar', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def aceptar_reserva(id_reserva):
    reserva = db.session.get(Reserva, id_reserva)
    comprobante = _comprobante_por_validar(reserva)
    if comprobante is None:
        return jsonify(error='Esta reserva no tiene un comprobante por validar'), 400

    comprobante.estado = 'aceptado'
    comprobante.id_validador = session['id_usuario']
    comprobante.fecha_validacion = datetime.now()
    reserva.estado = 'confirmada'
    db.session.commit()
    return jsonify(_reserva_a_dict(reserva, con_cliente=True))


@comprobante_bp.route('/api/reservas/<int:id_reserva>/rechazar', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def rechazar_reserva(id_reserva):
    """Body JSON: {"motivo": "El monto no coincide"}. La reserva vuelve a
    'pendiente' para que el cliente pueda subir otra captura."""
    reserva = db.session.get(Reserva, id_reserva)
    comprobante = _comprobante_por_validar(reserva)
    if comprobante is None:
        return jsonify(error='Esta reserva no tiene un comprobante por validar'), 400

    error = rechazar_comprobante(reserva, comprobante)
    if error:
        return jsonify(error=error), 400
    return jsonify(_reserva_a_dict(reserva, con_cliente=True))