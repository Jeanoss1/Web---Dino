"""Reportes de ventas (diario/semanal/mensual, por sede, por cajero, Yape vs
efectivo) y cuadre diario (dinero + minutos de Hoyos Rubio)."""

from datetime import datetime

from flask import Blueprint, jsonify, render_template, request

from app.controllers.decoradores import rol_requerido
from app.servicios_cuadre import cuadre_diario
from app.servicios_reportes import ErrorReporte, generar_reporte


reportes_bp = Blueprint('reportes', __name__)


def _fecha(valor, nombre):
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        raise ErrorReporte(f'{nombre} debe tener el formato AAAA-MM-DD')


@reportes_bp.route('/admin/reportes')
@rol_requerido('administrador')
def pagina_reportes():
    return render_template('admin_reportes.html')


@reportes_bp.route('/admin/cuadre')
@rol_requerido('administrador')
def pagina_cuadre():
    return render_template('admin_cuadre.html')


@reportes_bp.route('/api/admin/reportes/ventas')
@rol_requerido('administrador')
def api_reporte_ventas():
    """?id_sucursal=&rango=diario|semanal|mensual|personalizado&referencia=AAAA-MM-DD&desde=&hasta="""

    try:
        referencia = _fecha(request.args['referencia'], 'referencia') if request.args.get('referencia') else None
        desde = _fecha(request.args['desde'], 'desde') if request.args.get('desde') else None
        hasta = _fecha(request.args['hasta'], 'hasta') if request.args.get('hasta') else None

        reporte = generar_reporte(
            id_sucursal=request.args.get('id_sucursal', type=int),
            rango=request.args.get('rango', 'semanal'),
            referencia=referencia, desde=desde, hasta=hasta,
        )
    except ErrorReporte as e:
        return jsonify(error=str(e)), 400

    return jsonify(reporte)


@reportes_bp.route('/api/admin/cuadre')
@rol_requerido('administrador')
def api_cuadre():
    """?fecha=AAAA-MM-DD&id_sucursal="""
    try:
        fecha = _fecha(request.args['fecha'], 'fecha') if request.args.get('fecha') else datetime.now().date()
    except ErrorReporte as e:
        return jsonify(error=str(e)), 400

    return jsonify(cuadre_diario(fecha, id_sucursal=request.args.get('id_sucursal', type=int)))
