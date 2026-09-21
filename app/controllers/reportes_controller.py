from datetime import date

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from app.controllers.decoradores import rol_requerido, usuario_actual
from app.database import db
from app.models.Sucursal import Sucursal
from app.services import cuadre, lecturas, reportes
from app.services import validadores as v
from app.services.errores import ErrorNegocio

reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

SOLO_ADMIN = ('administrador',)


def _filtros(rango_defecto='semanal'):
    """Lee sede y rango (semanal / mensual / personalizado) de la URL."""
    id_sucursal = request.args.get('sede') or None
    if id_sucursal:
        id_sucursal = v.entero(id_sucursal, 'sede', 1, 10**9)
    rango = request.args.get('rango', rango_defecto)
    if rango not in ('diario', 'semanal', 'mensual', 'personalizado'):
        raise ErrorNegocio('Rango no válido.')
    desde, hasta, etiqueta = reportes.resolver_rango(
        rango, request.args.get('desde'), request.args.get('hasta'),
        request.args.get('ref') or (request.args.get('desde') if rango == 'diario' else None))
    return id_sucursal, rango, desde, hasta, etiqueta


def _contexto():
    id_sucursal, rango, desde, hasta, etiqueta = _filtros()
    return {
        'sedes': Sucursal.query.order_by(Sucursal.nombre).all(), 'sede_sel': id_sucursal,
        'rango': rango, 'desde': desde, 'hasta': hasta,
        'ref': request.args.get('ref', ''),
        'r': reportes.generar(desde, hasta, id_sucursal, etiqueta),
        'consulta': request.query_string.decode(),
    }


@reportes_bp.route('/dashboard')
@rol_requerido(*SOLO_ADMIN)
def dashboard():
    ctx = _contexto()
    hoy = cuadre.cuadre_diario(date.today(), ctx['sede_sel'])
    return render_template('reportes/dashboard.html', pagina_activa='dashboard',
                           alertas_hoy=hoy['total_alertas'],
                           alertas_contadores=lecturas.alertas_del_dia(date.today(), ctx['sede_sel']), **ctx)


@reportes_bp.route('/')
@rol_requerido(*SOLO_ADMIN)
def ventas():
    return render_template('reportes/ventas.html', pagina_activa='reportes', **_contexto())


@reportes_bp.route('/cuadre')
@rol_requerido(*SOLO_ADMIN)
def pagina_cuadre():
    dia = v.fecha(request.args.get('fecha')) if request.args.get('fecha') else date.today()
    id_sucursal = request.args.get('sede') or None
    if id_sucursal:
        id_sucursal = v.entero(id_sucursal, 'sede', 1, 10**9)
    return render_template(
        'reportes/cuadre.html', pagina_activa='cuadre', c=cuadre.cuadre_diario(dia, id_sucursal),
        sedes=Sucursal.query.order_by(Sucursal.nombre).all(), sede_sel=id_sucursal, fecha=dia,
    )


def _contexto_contadores():
    id_sucursal, rango, desde, hasta, etiqueta = _filtros('diario')
    solo = bool(request.args.get('solo_alertas'))
    return {
        'sedes': Sucursal.query.order_by(Sucursal.nombre).all(), 'sede_sel': id_sucursal, 'rango': rango,
        'desde': desde, 'hasta': hasta, 'etiqueta': etiqueta, 'solo_alertas': solo,
        'c': lecturas.cuadre_atracciones(desde, hasta, id_sucursal, solo),
        'consulta': request.query_string.decode(),
    }


@reportes_bp.route('/contadores')
@rol_requerido(*SOLO_ADMIN)
def contadores():
    return render_template('reportes/contadores.html', pagina_activa='contadores', **_contexto_contadores())


@reportes_bp.route('/contadores/exportar/<formato>')
@rol_requerido(*SOLO_ADMIN)
def exportar_contadores(formato):
    if formato not in ('excel', 'pdf'):
        raise ErrorNegocio('Formato no válido.', 404)
    ctx = _contexto_contadores()
    sede = db.session.get(Sucursal, ctx['sede_sel']).nombre if ctx['sede_sel'] else 'Todas las sedes'
    titulo = f'Cuadre de contadores · {ctx["etiqueta"]} · {sede}'
    nombre = f'contadores_{ctx["desde"]:%Y%m%d}_{ctx["hasta"]:%Y%m%d}'
    if formato == 'excel':
        return Response(reportes.exportar_contadores_excel(ctx['c'], titulo),
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition': f'attachment; filename={nombre}.xlsx'})
    return Response(reportes.exportar_contadores_pdf(ctx['c'], titulo), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={nombre}.pdf'})


@reportes_bp.route('/contadores/<int:id_lectura>/ajustar', methods=['POST'])
@rol_requerido(*SOLO_ADMIN)
def ajustar_lectura(id_lectura):
    lecturas.ajustar(id_lectura, request.form.get('lectura_final'), request.form.get('nota'), usuario_actual())
    flash('Lectura ajustada y justificada.', 'exito')
    return redirect(request.referrer or url_for('reportes.contadores'))


@reportes_bp.route('/exportar/<formato>')
@rol_requerido(*SOLO_ADMIN)
def exportar(formato):
    if formato not in ('excel', 'pdf'):
        raise ErrorNegocio('Formato no válido.', 404)
    id_sucursal, rango, desde, hasta, etiqueta = _filtros()
    r = reportes.generar(desde, hasta, id_sucursal, etiqueta)
    sede = db.session.get(Sucursal, id_sucursal).nombre if id_sucursal else None
    nombre = f'reporte_ventas_{desde:%Y%m%d}_{hasta:%Y%m%d}'
    if formato == 'excel':
        return Response(
            reportes.exportar_excel(r, sede),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename={nombre}.xlsx'})
    return Response(reportes.exportar_pdf(r, sede), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={nombre}.pdf'})
