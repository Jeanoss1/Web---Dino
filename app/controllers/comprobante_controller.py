import hashlib
import os
import uuid
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


def _extension_por_firma(cabecera):
    """Detecta el tipo real de imagen por su contenido (no por el nombre)."""
    if cabecera.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if cabecera.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return 'webp'
    return None


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
    if reserva.estado == 'cancelada':
        return jsonify(error='Esta reserva fue cancelada'), 400
    if reserva.estado == 'confirmada':
        return jsonify(error='Esta reserva ya está confirmada'), 400
    if reserva.estado == 'por_validar':
        return jsonify(error='Ya enviaste un comprobante, el cajero lo está revisando'), 400

    archivo = request.files.get('comprobante')
    if archivo is None or not archivo.filename:
        return jsonify(error='Selecciona la captura de tu pago'), 400
    contenido = archivo.read()
    if not contenido:
        return jsonify(error='El archivo está vacío'), 400
    extension = _extension_por_firma(contenido[:16])
    if extension is None:
        return jsonify(error='Sube una imagen PNG, JPG o WEBP'), 400

    huella = hashlib.sha256(contenido).hexdigest()
    repetido = (
        ComprobanteReserva.query
        .filter(ComprobanteReserva.hash_archivo == huella,
                ComprobanteReserva.id_reserva != reserva.id_reserva,
                ComprobanteReserva.estado.in_(['por_validar', 'aceptado']))
        .first()
    )
    if repetido:
        return jsonify(error='Esta captura ya fue usada en otra reserva'), 400

    # El nombre lo generamos nosotros: nunca se usa el nombre que envía el usuario
    carpeta = current_app.config['UPLOAD_FOLDER']
    os.makedirs(carpeta, exist_ok=True)
    nombre = f'reserva{reserva.id_reserva}_{uuid.uuid4().hex}.{extension}'
    with open(os.path.join(carpeta, nombre), 'wb') as f:
        f.write(contenido)

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

    datos = request.get_json(silent=True) or {}
    motivo = (datos.get('motivo') or '').strip()
    if not motivo:
        return jsonify(error='Indica el motivo del rechazo'), 400

    comprobante.estado = 'rechazado'
    comprobante.motivo_rechazo = motivo[:200]
    comprobante.id_validador = session['id_usuario']
    comprobante.fecha_validacion = datetime.now()
    reserva.estado = 'pendiente'
    db.session.commit()
    return jsonify(_reserva_a_dict(reserva, con_cliente=True))