from datetime import date, timedelta

from flask import (Blueprint, Response, flash, redirect, render_template,
                   request, url_for)

from app.controllers.decoradores import rol_requerido, usuario_actual
from app.database import db
from app.models.Flota import Flota
from app.models.Sucursal import Sucursal
from app.models.usuario import Usuario
from app.services import catalogo, lecturas, tarifas, turnos, usuarios
from app.services import validadores as v
from app.services.errores import ErrorNegocio

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.before_request
@rol_requerido('administrador')
def _solo_administrador():
    """Todo el módulo es exclusivo del administrador."""


@admin_bp.route('/')
def inicio():
    return redirect(url_for('reportes.dashboard'))


# ------------------------------------------------------------------ usuarios
@admin_bp.route('/usuarios')
def lista_usuarios():
    return render_template(
        'admin/usuarios.html', pagina_activa='usuarios',
        usuarios=Usuario.query.order_by(Usuario.id_rol, Usuario.nombre).all(),
        sedes=Sucursal.query.order_by(Sucursal.nombre).all(),
    )


@admin_bp.route('/usuarios', methods=['POST'])
def crear_usuario():
    usuario = usuarios.crear_personal(request.form)
    flash(f'Cuenta creada para {usuario.nombre_completo}.', 'exito')
    return redirect(url_for('admin.lista_usuarios'))


@admin_bp.route('/usuarios/<int:id_usuario>/estado', methods=['POST'])
def estado_usuario(id_usuario):
    u = usuarios.cambiar_estado(id_usuario, usuario_actual().id_usuario)
    flash(f'Cuenta de {u.nombre_completo} {"activada" if u.estado else "desactivada"}.', 'exito')
    return redirect(url_for('admin.lista_usuarios'))


@admin_bp.route('/usuarios/<int:id_usuario>/contrasena', methods=['POST'])
def clave_usuario(id_usuario):
    usuarios.resetear_contrasena(id_usuario, request.form.get('contrasena'))
    flash('Contraseña actualizada.', 'exito')
    return redirect(url_for('admin.lista_usuarios'))


@admin_bp.route('/usuarios/<int:id_usuario>/cajero', methods=['POST'])
def editar_cajero(id_usuario):
    usuarios.actualizar_cajero(id_usuario, request.form.get('id_sucursal'), request.form.get('tipo_turno'))
    flash('Sede y turno del cajero actualizados.', 'exito')
    return redirect(url_for('admin.lista_usuarios'))


# --------------------------------------------------------------------- sedes
@admin_bp.route('/sedes')
def lista_sedes():
    return render_template('admin/sedes.html', pagina_activa='sedes',
                           sedes=Sucursal.query.order_by(Sucursal.nombre).all())


@admin_bp.route('/sedes', methods=['POST'])
def crear_sede():
    catalogo.crear_sede(request.form.get('nombre'), request.form.get('direccion'),
                        activa=bool(request.form.get('activa')))
    flash('Sede creada.', 'exito')
    return redirect(url_for('admin.lista_sedes'))


@admin_bp.route('/sedes/<int:id_sucursal>/estado', methods=['POST'])
def estado_sede(id_sucursal):
    sede = catalogo.alternar_sede(id_sucursal)
    flash(f'Sede {sede.nombre} {"activada" if sede.estado == "activa" else "desactivada"}.', 'exito')
    return redirect(url_for('admin.lista_sedes'))


# --------------------------------------------------------------------- flota
@admin_bp.route('/flota')
def lista_flota():
    return render_template(
        'admin/flota.html', pagina_activa='flota',
        flota=Flota.query.order_by(Flota.id_sucursal, Flota.tipo, Flota.nombre).all(),
        sedes=Sucursal.query.order_by(Sucursal.nombre).all(), tarifa=tarifas.tarifa_vigente(),
        estados=catalogo.ESTADOS_FLOTA,
    )


@admin_bp.route('/flota', methods=['POST'])
def crear_unidad():
    unidad = catalogo.crear_unidad(request.form)
    flash(f'Unidad «{unidad.nombre}» agregada.', 'exito')
    return redirect(url_for('admin.lista_flota'))


@admin_bp.route('/flota/<int:id_flota>/estado', methods=['POST'])
def estado_unidad(id_flota):
    unidad = catalogo.cambiar_estado_unidad(id_flota, request.form.get('estado'))
    flash(f'«{unidad.nombre}» ahora está {unidad.estado}.', 'exito')
    return redirect(url_for('admin.lista_flota'))


@admin_bp.route('/flota/<int:id_flota>/contador', methods=['POST'])
def contador_unidad(id_flota):
    unidad = catalogo.cambiar_tipo_contador(id_flota, request.form.get('tipo_contador'))
    flash(f'«{unidad.nombre}» ahora cuenta {unidad.tipo_contador}.', 'exito')
    return redirect(url_for('admin.lista_flota'))


# -------------------------------------------------------------------- tarifas
@admin_bp.route('/tarifas')
def ver_tarifa():
    tarifa = tarifas.tarifa_vigente()
    editor = db.session.get(Usuario, tarifa.id_usuario) if tarifa.id_usuario else None
    return render_template('admin/tarifas.html', pagina_activa='tarifas', tarifa=tarifa, editor=editor,
                           tolerancias=lecturas.obtener_tolerancias())


@admin_bp.route('/parametros', methods=['POST'])
def editar_tolerancias():
    lecturas.guardar_tolerancias(request.form.get('tolerancia_minutos'), request.form.get('tolerancia_encendidos'))
    flash('Tolerancias de los contadores actualizadas.', 'exito')
    return redirect(url_for('admin.ver_tarifa'))


@admin_bp.route('/tarifas', methods=['POST'])
def editar_tarifa():
    t = tarifas.actualizar(request.form.get('precio'), request.form.get('minutos'), usuario_actual().id_usuario)
    flash(f'Tarifa actualizada: S/ {t.precio:.2f} por {t.minutos} minutos. '
          'Las ventas anteriores conservan su precio.', 'exito')
    return redirect(url_for('admin.ver_tarifa'))


# --------------------------------------------------------------------- turnos
def _lunes_param(nombre='semana'):
    texto = request.values.get(nombre)
    return turnos.lunes_de(v.fecha(texto) if texto else date.today())


@admin_bp.route('/turnos')
def horario_semanal():
    lunes = _lunes_param()
    sede = request.args.get('sede') or None
    sede = v.entero(sede, 'sede', 1, 10**9) if sede else None
    return render_template(
        'admin/turnos.html', pagina_activa='turnos', lunes=lunes, dias=turnos.dias_de_semana(lunes),
        nombres_dias=turnos.DIAS, cajeros=turnos.cajeros_activos(sede), turnos=turnos.turnos_activos(),
        asignaciones=turnos.asignaciones_de(lunes, sede), sedes=Sucursal.query.order_by(Sucursal.nombre).all(),
        sede_sel=sede, anterior=lunes - timedelta(days=7), siguiente=lunes + timedelta(days=7),
    )


@admin_bp.route('/turnos/guardar', methods=['POST'])
def guardar_horario():
    lunes = _lunes_param()
    seleccion = {}
    for clave, valor in request.form.items():
        if clave.startswith('t_'):                    # t_<id_cajero>_<AAAA-MM-DD>
            _, id_cajero, dia = clave.split('_', 2)
            seleccion[(int(id_cajero), v.fecha(dia))] = valor
    turnos.guardar_semana(lunes, seleccion)
    flash('Horario de la semana guardado.', 'exito')
    return redirect(url_for('admin.horario_semanal', semana=lunes.isoformat(),
                            sede=request.form.get('sede') or None))


@admin_bp.route('/turnos/copiar', methods=['POST'])
def copiar_horario():
    lunes = _lunes_param()
    cantidad = turnos.copiar_semana(lunes - timedelta(days=7), lunes, rotar=bool(request.form.get('rotar')))
    flash(f'Se copiaron {cantidad} asignaciones de la semana anterior.', 'exito')
    return redirect(url_for('admin.horario_semanal', semana=lunes.isoformat()))


@admin_bp.route('/turnos/importar', methods=['POST'])
def importar_horario():
    lunes = _lunes_param()
    archivo = request.files.get('archivo')
    if archivo is None or not archivo.filename:
        raise ErrorNegocio('Selecciona el archivo del horario (.csv o .xlsx).')
    cantidad = turnos.importar_horario(archivo, lunes)
    flash(f'Horario importado: {cantidad} asignaciones.', 'exito')
    return redirect(url_for('admin.horario_semanal', semana=lunes.isoformat()))


@admin_bp.route('/turnos/plantilla.csv')
def plantilla_horario():
    lunes = _lunes_param()
    return Response(turnos.plantilla_csv(lunes), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename=horario_{lunes:%Y%m%d}.csv'})
