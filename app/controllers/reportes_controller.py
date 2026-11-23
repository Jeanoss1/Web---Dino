"""Reportes de ventas (diario/semanal/mensual, por sede, por cajero, Yape vs
efectivo) y cuadre diario (dinero + minutos de Hoyos Rubio)."""

from datetime import datetime

from flask import Blueprint, Response, jsonify, render_template, request, session

from app.controllers.decoradores import rol_requerido
from app.database import db
from app.models.Sucursal import Sucursal
from app.servicios_cuadre import cuadre_diario
from app.servicios_reporte_pdf import generar_pdf_reporte
from app.servicios_reportes import ErrorReporte, generar_reporte
from app.tiempo import hoy


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


def _reporte_de_la_consulta():
    """Arma el reporte con los filtros de la URL (lo usan la vista JSON y el PDF):
    ?id_sucursal=&rango=diario|semanal|mensual|personalizado&referencia=AAAA-MM-DD&desde=&hasta="""
    args = request.args
    fechas = {
        nombre: _fecha(args[nombre], nombre) if args.get(nombre) else None
        for nombre in ('referencia', 'desde', 'hasta')
    }
    return generar_reporte(
        id_sucursal=args.get('id_sucursal', type=int),
        rango=args.get('rango', 'semanal'),
        **fechas,
    )


@reportes_bp.route('/api/admin/reportes/ventas')
@rol_requerido('administrador')
def api_reporte_ventas():
    try:
        return jsonify(_reporte_de_la_consulta())
    except ErrorReporte as e:
        return jsonify(error=str(e)), 400


@reportes_bp.route('/api/admin/reportes/ventas/pdf')
@rol_requerido('administrador')
def api_reporte_ventas_pdf():
    """CA08.4: mismo reporte y mismos filtros que /api/admin/reportes/ventas, en PDF."""
    try:
        reporte = _reporte_de_la_consulta()
    except ErrorReporte as e:
        return jsonify(error=str(e)), 400

    id_sucursal = request.args.get('id_sucursal', type=int)
    sucursal = db.session.get(Sucursal, id_sucursal) if id_sucursal else None
    contenido = generar_pdf_reporte(
        reporte, request.args.get('rango', 'semanal'),
        sucursal.nombre if sucursal else None,
        session.get('nombre') or session.get('correo'),
    )
    nombre = f"reporte_ventas_{reporte['inicio']}_{reporte['fin']}.pdf"
    return Response(contenido, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{nombre}"'})


@reportes_bp.route('/api/admin/cuadre')
@rol_requerido('administrador')
def api_cuadre():
    """?fecha=AAAA-MM-DD&id_sucursal="""
    try:
        fecha = _fecha(request.args['fecha'], 'fecha') if request.args.get('fecha') else hoy()
    except ErrorReporte as e:
        return jsonify(error=str(e)), 400

    return jsonify(cuadre_diario(fecha, id_sucursal=request.args.get('id_sucursal', type=int)))
