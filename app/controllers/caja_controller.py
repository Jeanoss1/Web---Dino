from datetime import date

from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, url_for)

from app.controllers.decoradores import (alcance_sede, cajero_actual,
                                         rol_requerido, usuario_actual)
from app.models.Caja import Caja
from app.models.Turno import AsignacionTurno
from app.services import cajas, lecturas, reservas

caja_bp = Blueprint('caja', __name__)

CAJA = ('cajero', 'administrador')


# ------------------------------------------------------- caja del cajero
@caja_bp.route('/caja')
@rol_requerido('cajero')
def panel():
    cajero = cajero_actual()
    usuario = usuario_actual()
    caja = cajas.caja_abierta(usuario.id_usuario)
    turno_hoy = AsignacionTurno.query.filter_by(id_cajero=cajero.id_cajero, fecha=date.today()).first()
    cierres = (Caja.query.filter_by(id_usuario=usuario.id_usuario, estado='cerrada')
               .order_by(Caja.id_caja.desc()).limit(5).all())
    apertura, omitidas = lecturas.preparar_apertura(cajero.id_sucursal)
    return render_template(
        'caja/panel.html', cajero=cajero, caja=caja, turno_hoy=turno_hoy, cierres=cierres,
        resumen=cajas.resumen(caja) if caja else None, pagina_activa='caja',
        unidades_apertura=apertura, omitidas=omitidas,
        lecturas_caja=[l for l in caja.lecturas if l.flota.estado == 'disponible'] if caja else [],
    )


@caja_bp.route('/caja/abrir', methods=['POST'])
@rol_requerido('cajero')
def abrir():
    cajas.abrir(usuario_actual(), cajero_actual(), request.form.get('monto_inicial'), request.form)
    flash('Caja abierta. ¡Buen turno!', 'exito')
    return redirect(url_for('caja.panel'))


@caja_bp.route('/caja/movimiento', methods=['POST'])
@rol_requerido('cajero')
def movimiento():
    cajero_actual()
    cajas.registrar_movimiento(
        cajas.caja_abierta(usuario_actual().id_usuario), request.form.get('tipo'),
        request.form.get('monto'), request.form.get('descripcion'),
    )
    flash('Movimiento registrado.', 'exito')
    return redirect(url_for('caja.panel'))


@caja_bp.route('/caja/cerrar', methods=['POST'])
@rol_requerido('cajero')
def cerrar():
    cajero_actual()
    caja = cajas.cerrar(
        cajas.caja_abierta(usuario_actual().id_usuario),
        request.form.get('monto_contado'), request.form.get('observacion'), request.form,
    )
    con_alerta = [l.flota.nombre for l in caja.lecturas if l.alerta]
    tipo = 'exito' if abs(caja.diferencia) < 0.01 and not con_alerta else 'aviso'
    flash(f'Caja cerrada. Esperado S/ {caja.efectivo_esperado:.2f} · contado S/ {caja.monto_final:.2f} '
          f'· diferencia S/ {caja.diferencia:.2f}. Minutos vendidos {caja.minutos_vendidos} / '
          f'usados {caja.minutos_usados}.', tipo)
    if con_alerta:
        flash('Atracciones con diferencia en el contador (se avisó al administrador): '
              + ', '.join(con_alerta) + '.', 'aviso')
    return redirect(url_for('caja.panel'))


# ------------------------------------------------- validación de pagos Yape
@caja_bp.route('/caja/validaciones')
@rol_requerido(*CAJA)
def pagina_validaciones():
    return render_template('validar_reservas.html', pagina_activa='validaciones')


@caja_bp.route('/api/caja/reservas')
@rol_requerido(*CAJA)
def listar_reservas():
    """?estado=pago_en_revision (por defecto) | confirmada | rechazada. Solo la sede del cajero."""
    lista = reservas.listar_para_caja(alcance_sede(), request.args.get('estado', 'pago_en_revision'))
    return jsonify([reservas.reserva_a_dict(r, con_cliente=True) for r in lista])


@caja_bp.route('/api/reservas/<int:id_reserva>/aceptar', methods=['POST'])
@rol_requerido(*CAJA)
def aceptar_reserva(id_reserva):
    r = reservas.aceptar(id_reserva, usuario_actual(), alcance_sede())
    return jsonify(reservas.reserva_a_dict(r, con_cliente=True))


@caja_bp.route('/api/reservas/<int:id_reserva>/rechazar', methods=['POST'])
@rol_requerido(*CAJA)
def rechazar_reserva(id_reserva):
    """Body JSON: {"motivo": "El monto no coincide"}. La reserva queda «rechazada»."""
    datos = request.get_json(silent=True) or {}
    r = reservas.rechazar(id_reserva, usuario_actual(), alcance_sede(), datos.get('motivo'))
    return jsonify(reservas.reserva_a_dict(r, con_cliente=True))
