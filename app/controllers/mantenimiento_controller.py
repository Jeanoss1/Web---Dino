from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.controllers.decoradores import rol_requerido
from app.models.Flota import Flota
from app.models.Mantenimiento import Mantenimiento
from app.models.Repuesto import Repuesto
from app.services import catalogo

mantenimiento_bp = Blueprint('mantenimiento', __name__, url_prefix='/admin/mantenimiento')


@mantenimiento_bp.before_request
@rol_requerido('administrador')
def _solo_administrador():
    """El mantenimiento y los repuestos son exclusivos del administrador."""


@mantenimiento_bp.route('/')
def pagina():
    return render_template(
        'admin/mantenimiento.html', pagina_activa='mantenimiento',
        flota=Flota.query.order_by(Flota.nombre).all(),
        repuestos=Repuesto.query.order_by(Repuesto.nombre).all(),
        mantenimientos=Mantenimiento.query.order_by(Mantenimiento.id_mantenimiento.desc()).limit(30).all(),
    )


@mantenimiento_bp.route('/iniciar', methods=['POST'])
def iniciar():
    mant = catalogo.iniciar_mantenimiento(request.form)
    flash(f'«{mant.flota.nombre}» pasó a mantenimiento.', 'exito')
    return redirect(url_for('mantenimiento.pagina'))


@mantenimiento_bp.route('/<int:id_mantenimiento>/finalizar', methods=['POST'])
def finalizar(id_mantenimiento):
    catalogo.finalizar_mantenimiento(id_mantenimiento)
    flash('Mantenimiento finalizado; la unidad vuelve a estar disponible.', 'exito')
    return redirect(url_for('mantenimiento.pagina'))


@mantenimiento_bp.route('/repuestos', methods=['POST'])
def crear_repuesto():
    catalogo.crear_repuesto(request.form.get('nombre'), request.form.get('stock', 0),
                            request.form.get('stock_minimo', 0))
    flash('Repuesto registrado.', 'exito')
    return redirect(url_for('mantenimiento.pagina'))


@mantenimiento_bp.route('/repuestos/<int:id_repuesto>/stock', methods=['POST'])
def sumar_stock(id_repuesto):
    catalogo.sumar_stock(id_repuesto, request.form.get('cantidad'))
    flash('Stock actualizado.', 'exito')
    return redirect(url_for('mantenimiento.pagina'))
