from datetime import date

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)

from app.controllers.decoradores import (cajero_actual, rol_requerido,
                                         usuario_actual)
from app.database import db
from app.models.Flota import Flota
from app.models.RegistroUso import RegistroUso
from app.models.Venta import Venta
from app.services import cajas, uso, ventas
from app.services.tarifas import tarifa_vigente

venta_bp = Blueprint('venta', __name__)


@venta_bp.route('/caja/venta')
@rol_requerido('cajero')
def nueva_venta():
    cajero = cajero_actual()
    usuario = usuario_actual()
    uso.finalizar_vencidos(cajero.id_sucursal)
    en_uso = {u.id_flota for u in RegistroUso.query.filter_by(
        id_sucursal=cajero.id_sucursal, estado='en_curso')}
    unidades = (Flota.query.filter_by(id_sucursal=cajero.id_sucursal, estado='disponible')
                .order_by(Flota.tipo, Flota.nombre).all())
    return render_template(
        'caja/venta.html', cajero=cajero, unidades=unidades, en_uso=en_uso,
        tarifa=tarifa_vigente(), caja=cajas.caja_abierta(usuario.id_usuario),
        ventas_hoy=ventas.ventas_del_dia(usuario.id_usuario), pagina_activa='venta',
    )


@venta_bp.route('/caja/venta', methods=['POST'])
@rol_requerido('cajero')
def registrar_venta():
    venta = ventas.crear_venta_presencial(
        usuario_actual(), cajero_actual(), request.form.get('id_flota'),
        request.form.get('bloques'), request.form.get('metodo_pago'),
    )
    fin = venta.detalles[0].usos[0].hora_fin_prevista
    flash(f'Venta #{venta.id_venta} registrada: S/ {venta.total:.2f} por {venta.minutos} minutos. '
          f'El tiempo ya corre y terminará solo a las {fin:%H:%M}.', 'exito')
    return redirect(url_for('venta.ticket', id_venta=venta.id_venta))


@venta_bp.route('/caja/venta/<int:id_venta>')
@rol_requerido('cajero', 'administrador')
def ticket(id_venta):
    """Comprobante imprimible; el cajero solo ve ventas de su sede."""
    venta = db.session.get(Venta, id_venta)
    usuario = usuario_actual()
    if venta is None or (usuario.rol_nombre == 'cajero'
                         and venta.id_sucursal != cajero_actual().id_sucursal):
        abort(404)
    return render_template('caja/ticket.html', venta=venta, pagina_activa='venta')


@venta_bp.route('/caja/uso')
@rol_requerido('cajero')
def pagina_uso():
    cajero = cajero_actual()
    return render_template(
        'caja/uso.html', cajero=cajero, detalles=uso.detalles_del_dia(cajero.id_sucursal),
        hoy=date.today(), pagina_activa='uso',
    )


@venta_bp.route('/caja/uso/iniciar', methods=['POST'])
@rol_requerido('cajero')
def iniciar_uso():
    uso.iniciar(usuario_actual(), cajero_actual(), request.form.get('id_detalle'))
    flash('Tiempo iniciado.', 'exito')
    return redirect(url_for('venta.pagina_uso'))


@venta_bp.route('/caja/uso/<int:id_uso>/finalizar', methods=['POST'])
@rol_requerido('cajero')
def finalizar_uso(id_uso):
    registro = uso.finalizar_antes(cajero_actual(), id_uso, request.form.get('motivo'))
    flash(f'Alquiler finalizado antes de tiempo: {registro.minutos_usados} minutos registrados.', 'aviso')
    return redirect(url_for('venta.pagina_uso'))
