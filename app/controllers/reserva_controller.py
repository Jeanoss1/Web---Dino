from flask import (Blueprint, current_app, jsonify, render_template, request,
                   send_from_directory)

from app.controllers.decoradores import (alcance_sede, login_requerido,
                                         rol_requerido, usuario_actual)
from app.services import franjas, reservas

reserva_bp = Blueprint('reserva', __name__)


# ------------------------------------------------------------------- páginas
@reserva_bp.route('/disponibilidad')
@rol_requerido('cliente')
def disponibilidad():
    return render_template('disponibilidad.html')


@reserva_bp.route('/mis-reservas')
@rol_requerido('cliente')
def pagina_mis_reservas():
    return render_template('mis_reservas.html')


# ----------------------------------------------------------------------- API
@reserva_bp.route('/api/franjas')
@login_requerido
def listar_franjas():
    """?id_flota=1&fecha=AAAA-MM-DD  ->  franjas libres de la unidad."""
    lista = franjas.listar_disponibles(request.args.get('id_flota'), request.args.get('fecha'))
    return jsonify([
        {'id_franja': f.id_franja, 'id_flota': f.id_flota,
         'horario_inicio': f.horario_inicio.isoformat(), 'horario_fin': f.horario_fin.isoformat(),
         'capacidad': f.capacidad}
        for f in lista
    ])


@reserva_bp.route('/api/reservas', methods=['POST'])
@rol_requerido('cliente')
def crear_reserva():
    """Body JSON: {"cantidad_personas": 2, "items": [{"id_flota": 1, "id_franja": 3}]}"""
    cliente = reservas.cliente_de(usuario_actual())
    reserva = reservas.crear_reserva(cliente, request.get_json(silent=True) or {})
    return jsonify(reservas.reserva_a_dict(reserva)), 201


@reserva_bp.route('/api/mis-reservas')
@rol_requerido('cliente')
def mis_reservas():
    cliente = reservas.cliente_de(usuario_actual())
    return jsonify([reservas.reserva_a_dict(r) for r in reservas.listar_del_cliente(cliente)])


@reserva_bp.route('/api/reservas/<int:id_reserva>/comprobante', methods=['POST'])
@rol_requerido('cliente')
def subir_comprobante(id_reserva):
    cliente = reservas.cliente_de(usuario_actual())
    reserva = reservas.subir_comprobante(cliente, id_reserva, request.files.get('comprobante'))
    return jsonify(reservas.reserva_a_dict(reserva)), 201


@reserva_bp.route('/api/reservas/<int:id_reserva>/cancelar', methods=['POST'])
@rol_requerido('cliente')
def cancelar_reserva(id_reserva):
    cliente = reservas.cliente_de(usuario_actual())
    return jsonify(reservas.reserva_a_dict(reservas.cancelar(cliente, id_reserva)))


@reserva_bp.route('/comprobantes/<int:id_comprobante>')
@login_requerido
def ver_comprobante(id_comprobante):
    """La captura la ve solo su dueño o el personal de la sede de la reserva."""
    usuario = usuario_actual()
    alcance = alcance_sede() if usuario.rol_nombre != 'cliente' else None
    comprobante = reservas.comprobante_visible(id_comprobante, usuario, alcance)
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], comprobante.archivo)
