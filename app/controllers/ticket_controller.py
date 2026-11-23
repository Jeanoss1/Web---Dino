"""Tickets de acceso de las reservas en línea (HU03 y HU05)."""
from flask import Blueprint, abort, jsonify, render_template, request, session

from app.controllers.decoradores import login_requerido, rol_requerido
from app.models.Cliente import Cliente
from app.models.Ticket import Ticket
from app.servicios_ticket import ticket_a_dict, usar_ticket, validar_ticket

ticket_bp = Blueprint('ticket', __name__)

ROLES_CAJA = ('administrador', 'cajero')

# Datos de la empresa que se imprimen en el ticket y en los reportes
EMPRESA = {
    'razon_social': 'Dino Park Perú S.A.C.',
    'ruc': '20608934512',
}


def _sede_del_cajero():
    """El administrador valida en cualquier sede; el cajero solo en la suya."""
    return session.get('id_sucursal') if session.get('rol') == 'cajero' else None


@ticket_bp.route('/tickets/<codigo>')
@login_requerido
def ver_ticket(codigo):
    """Ticket imprimible. Lo ve su cliente y el personal de caja."""
    ticket = Ticket.query.filter_by(codigo=codigo.upper()).first()
    if ticket is None or ticket.reserva is None:
        abort(404)
    if session.get('rol') not in ROLES_CAJA:
        cliente = Cliente.query.filter_by(correo=session.get('correo')).first()
        if cliente is None or cliente.id_cliente != ticket.reserva.id_cliente:
            abort(404)
    datos = ticket_a_dict(ticket)
    sede = ticket.reserva.detalles[0].flota.sucursal if ticket.reserva.detalles else None
    return render_template('ticket.html', t=datos, empresa=EMPRESA, sede=sede)


@ticket_bp.route('/api/caja/tickets/validar', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def validar():
    """Body JSON: {"codigo": "T260917-A1B2C3"}. CA05.4 y CA05.5."""
    codigo = (request.get_json(silent=True) or {}).get('codigo')
    ticket, error, http = validar_ticket(codigo, _sede_del_cajero())
    if error:
        cuerpo = {'error': error}
        if ticket is not None and http == 409:
            cuerpo['ticket'] = ticket_a_dict(ticket)
        return jsonify(cuerpo), http
    return jsonify(ticket_a_dict(ticket))


@ticket_bp.route('/api/caja/tickets/<codigo>/usar', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def usar(codigo):
    """Asigna las unidades de la reserva y marca el ticket como usado."""
    ticket, error, http = validar_ticket(codigo, _sede_del_cajero())
    if error:
        return jsonify(error=error), http
    error = usar_ticket(ticket, session['id_usuario'])
    if error:
        return jsonify(error=error), 409
    return jsonify(ticket_a_dict(ticket))
