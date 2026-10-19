"""Panel del administrador: activar/desactivar sedes y editar precios,
duraciones y paquetes de cada una, más el reporte de ventas por sede y por
cajero. Primer panel de administración del sistema (antes el administrador
veía la misma página pública que cualquier visitante)."""

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, render_template, request, session
from werkzeug.security import generate_password_hash

from app.controllers.decoradores import rol_requerido
from app.database import db

from app.models.AsignacionTurno import AsignacionTurno
from app.models.Caja import Caja
from app.models.Cliente import Cliente
from app.models.Flota import Carro, Dinosaurio, Flota, Moto, Otros
from app.models.PaqueteTarifa import PaqueteTarifa
from app.models.Rol import Rol
from app.models.Sucursal import Sucursal
from app.models.TurnoLaboral import TurnoLaboral
from app.models.usuario import Usuario
from app.models.Zona import Zona


admin_bp = Blueprint('admin', __name__)

CLASES_FLOTA = {
    'dinosaurio': Dinosaurio,
    'carro': Carro,
    'moto': Moto,
    'otros': Otros,
}


# ============================================================
# PÁGINAS
# ============================================================

@admin_bp.route('/admin')
@rol_requerido('administrador')
def pagina_admin():
    return render_template('admin_dashboard.html')


@admin_bp.route('/admin/sedes')
@rol_requerido('administrador')
def pagina_admin_sedes():
    return render_template('admin_sedes.html')


@admin_bp.route('/admin/usuarios')
@rol_requerido('administrador')
def pagina_admin_usuarios():
    return render_template('admin_usuarios.html')


@admin_bp.route('/admin/horarios')
@rol_requerido('administrador')
def pagina_admin_horarios():
    return render_template('admin_horarios.html')


# ============================================================
# SEDES / ZONAS / PAQUETES
# ============================================================

def _paquete_a_dict(p):
    return {
        'id_paquete': p.id_paquete,
        'id_zona': p.id_zona,
        'nombre': p.nombre,
        'tipo': p.tipo,
        'duracion_minutos': p.duracion_minutos,
        'precio': float(p.precio),
        'es_por_ninio': bool(p.es_por_ninio),
        'minimo_cantidad': p.minimo_cantidad,
        'estado': p.estado,
    }


def _zona_a_dict(z):
    return {
        'id_zona': z.id_zona,
        'id_sucursal': z.id_sucursal,
        'nombre': z.nombre,
        'descripcion': z.descripcion,
        'estado': z.estado,
        'paquetes': [_paquete_a_dict(p) for p in z.paquetes],
    }


def _sede_a_dict(s):
    return {
        'id_sucursal': s.id_sucursal,
        'nombre': s.nombre,
        'direccion': s.direccion,
        'estado': s.estado,
        'monto_adicional_exceso': (
            float(s.monto_adicional_exceso) if s.monto_adicional_exceso else None
        ),
        'zonas': [_zona_a_dict(z) for z in s.zonas],
    }


@admin_bp.route('/api/admin/sedes')
@rol_requerido('administrador')
def listar_sedes_admin():
    sedes = Sucursal.query.order_by(Sucursal.id_sucursal).all()
    return jsonify([_sede_a_dict(s) for s in sedes])


@admin_bp.route('/api/admin/sedes/<int:id_sucursal>', methods=['PUT'])
@rol_requerido('administrador')
def editar_sede(id_sucursal):
    sede = db.session.get(Sucursal, id_sucursal)
    if sede is None:
        return jsonify(error='Sede no encontrada'), 404

    datos = request.get_json(silent=True) or {}

    if 'nombre' in datos:
        nombre = (datos['nombre'] or '').strip()
        if not nombre:
            return jsonify(error='El nombre no puede estar vacío'), 400
        sede.nombre = nombre

    if 'direccion' in datos:
        sede.direccion = datos['direccion']

    if 'estado' in datos:
        if datos['estado'] not in ('activa', 'inactiva'):
            return jsonify(error="estado debe ser 'activa' o 'inactiva'"), 400
        sede.estado = datos['estado']

    if 'monto_adicional_exceso' in datos:
        valor = datos['monto_adicional_exceso']
        try:
            sede.monto_adicional_exceso = Decimal(str(valor)) if valor not in (None, '') else None
        except InvalidOperation:
            return jsonify(error='monto_adicional_exceso debe ser un número'), 400

    db.session.commit()
    return jsonify(_sede_a_dict(sede))


@admin_bp.route('/api/admin/zonas', methods=['POST'])
@rol_requerido('administrador')
def crear_zona():
    datos = request.get_json(silent=True) or {}
    id_sucursal = datos.get('id_sucursal')
    nombre = (datos.get('nombre') or '').strip()

    if not id_sucursal or not nombre:
        return jsonify(error='Indica id_sucursal y nombre'), 400

    if db.session.get(Sucursal, id_sucursal) is None:
        return jsonify(error='Sede no encontrada'), 404

    zona = Zona(
        id_sucursal=id_sucursal, nombre=nombre,
        descripcion=datos.get('descripcion'),
    )
    db.session.add(zona)
    db.session.commit()
    return jsonify(_zona_a_dict(zona)), 201


@admin_bp.route('/api/admin/zonas/<int:id_zona>', methods=['PUT'])
@rol_requerido('administrador')
def editar_zona(id_zona):
    zona = db.session.get(Zona, id_zona)
    if zona is None:
        return jsonify(error='Zona no encontrada'), 404

    datos = request.get_json(silent=True) or {}

    if 'nombre' in datos:
        nombre = (datos['nombre'] or '').strip()
        if not nombre:
            return jsonify(error='El nombre no puede estar vacío'), 400
        zona.nombre = nombre

    if 'descripcion' in datos:
        zona.descripcion = datos['descripcion']

    if 'estado' in datos:
        if datos['estado'] not in ('activa', 'inactiva'):
            return jsonify(error="estado debe ser 'activa' o 'inactiva'"), 400
        zona.estado = datos['estado']

    db.session.commit()
    return jsonify(_zona_a_dict(zona))


@admin_bp.route('/api/admin/paquetes', methods=['POST'])
@rol_requerido('administrador')
def crear_paquete():
    datos = request.get_json(silent=True) or {}
    id_zona = datos.get('id_zona')
    nombre = (datos.get('nombre') or '').strip()

    if not id_zona or not nombre:
        return jsonify(error='Indica id_zona y nombre'), 400

    if db.session.get(Zona, id_zona) is None:
        return jsonify(error='Zona no encontrada'), 404

    try:
        precio = Decimal(str(datos.get('precio')))
        if precio <= 0:
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        return jsonify(error='precio debe ser un número mayor a 0'), 400

    paquete = PaqueteTarifa(
        id_zona=id_zona,
        nombre=nombre,
        tipo=datos.get('tipo', 'individual'),
        duracion_minutos=datos.get('duracion_minutos'),
        precio=precio,
        es_por_ninio=bool(datos.get('es_por_ninio', True)),
        minimo_cantidad=int(datos.get('minimo_cantidad', 1)),
        orden=int(datos.get('orden', 0)),
    )
    db.session.add(paquete)
    db.session.commit()
    return jsonify(_paquete_a_dict(paquete)), 201


@admin_bp.route('/api/admin/paquetes/<int:id_paquete>', methods=['PUT'])
@rol_requerido('administrador')
def editar_paquete(id_paquete):
    paquete = db.session.get(PaqueteTarifa, id_paquete)
    if paquete is None:
        return jsonify(error='Paquete no encontrado'), 404

    datos = request.get_json(silent=True) or {}

    if 'nombre' in datos:
        nombre = (datos['nombre'] or '').strip()
        if not nombre:
            return jsonify(error='El nombre no puede estar vacío'), 400
        paquete.nombre = nombre

    if 'tipo' in datos:
        paquete.tipo = datos['tipo']

    if 'duracion_minutos' in datos:
        paquete.duracion_minutos = datos['duracion_minutos']

    if 'precio' in datos:
        try:
            precio = Decimal(str(datos['precio']))
            if precio <= 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return jsonify(error='precio debe ser un número mayor a 0'), 400
        paquete.precio = precio

    if 'es_por_ninio' in datos:
        paquete.es_por_ninio = bool(datos['es_por_ninio'])

    if 'minimo_cantidad' in datos:
        try:
            minimo = int(datos['minimo_cantidad'])
            if minimo < 1:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify(error='minimo_cantidad debe ser un entero mayor o igual a 1'), 400
        paquete.minimo_cantidad = minimo

    if 'estado' in datos:
        if datos['estado'] not in ('activa', 'inactiva'):
            return jsonify(error="estado debe ser 'activa' o 'inactiva'"), 400
        paquete.estado = datos['estado']

    db.session.commit()
    return jsonify(_paquete_a_dict(paquete))


# ============================================================
# FLOTA (atracciones de Real Plaza / Mega Plaza)
# ============================================================

def _flota_a_dict(f):
    extra = {
        'dinosaurio': lambda u: {'especie': u.especie},
        'carro': lambda u: {'velocidad': u.velocidad},
        'moto': lambda u: {'cilindrada': u.cilindrada},
        'otros': lambda u: {'descripcion': u.descripcion},
    }.get(f.tipo, lambda u: {})(f)

    return {
        'id_flota': f.id_flota,
        'id_sucursal': f.id_sucursal,
        'nombre': f.nombre,
        'tipo': f.tipo,
        'modelo': f.modelo,
        'estado': f.estado,
        'precio_hora': float(f.precio_hora or 0),
        'precio_alquiler': float(f.precio_alquiler) if f.precio_alquiler else None,
        'duracion_alquiler_minutos': f.duracion_alquiler_minutos or 12,
        'contador': f.contador_minutos if f.tipo == 'dinosaurio' else f.ciclos_uso,
        'unidad_contador': 'minutos' if f.tipo == 'dinosaurio' else 'encendidos',
        **extra,
    }


@admin_bp.route('/api/admin/flota')
@rol_requerido('administrador')
def listar_flota_admin():
    consulta = Flota.query
    id_sucursal = request.args.get('id_sucursal', type=int)
    if id_sucursal:
        consulta = consulta.filter_by(id_sucursal=id_sucursal)
    return jsonify([_flota_a_dict(f) for f in consulta.order_by(Flota.id_flota).all()])


@admin_bp.route('/api/admin/flota', methods=['POST'])
@rol_requerido('administrador')
def crear_flota():
    datos = request.get_json(silent=True) or {}
    tipo = datos.get('tipo')
    nombre = (datos.get('nombre') or '').strip()
    id_sucursal = datos.get('id_sucursal')

    if tipo not in CLASES_FLOTA:
        return jsonify(error=f"tipo debe ser uno de: {', '.join(CLASES_FLOTA)}"), 400
    if not nombre or not id_sucursal:
        return jsonify(error='Indica nombre e id_sucursal'), 400
    if db.session.get(Sucursal, id_sucursal) is None:
        return jsonify(error='Sede no encontrada'), 404

    try:
        precio_hora = Decimal(str(datos.get('precio_hora', 0)))
        precio_alquiler = Decimal(str(datos['precio_alquiler'])) if datos.get('precio_alquiler') else None
    except InvalidOperation:
        return jsonify(error='precio_hora/precio_alquiler deben ser números'), 400

    campo_extra = {
        'dinosaurio': 'especie', 'carro': 'velocidad',
        'moto': 'cilindrada', 'otros': 'descripcion',
    }[tipo]

    unidad = CLASES_FLOTA[tipo](
        nombre=nombre, modelo=datos.get('modelo'), id_sucursal=id_sucursal,
        precio_hora=precio_hora, estado=datos.get('estado', 'disponible'),
        precio_alquiler=precio_alquiler,
        duracion_alquiler_minutos=int(datos.get('duracion_alquiler_minutos', 12)),
        **{campo_extra: datos.get(campo_extra)},
    )
    db.session.add(unidad)
    db.session.commit()
    return jsonify(_flota_a_dict(unidad)), 201


@admin_bp.route('/api/admin/flota/<int:id_flota>', methods=['PUT'])
@rol_requerido('administrador')
def editar_flota(id_flota):
    unidad = db.session.get(Flota, id_flota)
    if unidad is None:
        return jsonify(error='La unidad no existe'), 404

    datos = request.get_json(silent=True) or {}

    if 'nombre' in datos:
        nombre = (datos['nombre'] or '').strip()
        if not nombre:
            return jsonify(error='El nombre no puede estar vacío'), 400
        unidad.nombre = nombre

    if 'modelo' in datos:
        unidad.modelo = datos['modelo']

    if 'precio_hora' in datos:
        try:
            precio = Decimal(str(datos['precio_hora']))
            if precio < 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return jsonify(error='precio_hora debe ser un número mayor o igual a 0'), 400
        unidad.precio_hora = precio

    if 'precio_alquiler' in datos:
        valor = datos['precio_alquiler']
        try:
            unidad.precio_alquiler = Decimal(str(valor)) if valor not in (None, '') else None
        except InvalidOperation:
            return jsonify(error='precio_alquiler debe ser un número'), 400

    if 'duracion_alquiler_minutos' in datos:
        try:
            duracion = int(datos['duracion_alquiler_minutos'])
            if duracion < 1:
                raise ValueError
        except (ValueError, TypeError):
            return jsonify(error='duracion_alquiler_minutos debe ser un entero mayor a 0'), 400
        unidad.duracion_alquiler_minutos = duracion

    if 'estado' in datos:
        if datos['estado'] not in ('disponible', 'mantenimiento', 'inactivo', 'alquilado'):
            return jsonify(error="estado debe ser 'disponible', 'mantenimiento', 'inactivo' o 'alquilado'"), 400
        unidad.estado = datos['estado']

    db.session.commit()
    return jsonify(_flota_a_dict(unidad))


# ============================================================
# USUARIOS (cajeros, clientes, administradores)
# ============================================================

def _usuario_a_dict(u):
    cliente = Cliente.query.filter_by(correo=u.correo).first() if u.rol and u.rol.nombre == 'cliente' else None
    sede = db.session.get(Sucursal, u.id_sucursal) if u.id_sucursal else None
    return {
        'id_usuario': u.id_usuario,
        'nombre': u.nombre,
        'apellido': u.apellido,
        'correo': u.correo,
        'rol': u.rol.nombre if u.rol else None,
        'estado': bool(u.estado),
        'proveedor': u.proveedor,
        'dni': cliente.dni if cliente else None,
        'telefono': cliente.telefono if cliente else None,
        'id_sucursal': u.id_sucursal,
        'sede': sede.nombre if sede else None,
    }


@admin_bp.route('/api/admin/usuarios')
@rol_requerido('administrador')
def listar_usuarios():
    consulta = Usuario.query.join(Rol)

    rol = request.args.get('rol')
    if rol:
        consulta = consulta.filter(Rol.nombre == rol)

    estado = request.args.get('estado')
    if estado in ('activo', 'inactivo'):
        consulta = consulta.filter(Usuario.estado == (estado == 'activo'))

    return jsonify([_usuario_a_dict(u) for u in consulta.order_by(Usuario.id_usuario).all()])


@admin_bp.route('/api/admin/usuarios', methods=['POST'])
@rol_requerido('administrador')
def crear_usuario_staff():
    """Crea cajero o administrador. Los clientes se registran desde /registro."""
    datos = request.get_json(silent=True) or {}

    rol_nombre = datos.get('rol')
    if rol_nombre not in ('cajero', 'administrador'):
        return jsonify(error="rol debe ser 'cajero' o 'administrador'"), 400

    nombre = (datos.get('nombre') or '').strip()
    apellido = (datos.get('apellido') or '').strip()
    correo = (datos.get('correo') or '').strip().lower()
    contrasena = datos.get('contrasena') or ''

    if not all([nombre, apellido, correo]) or len(contrasena) < 8:
        return jsonify(error='Completa nombre, apellido, correo y una contraseña de al menos 8 caracteres'), 400

    if Usuario.query.filter_by(correo=correo).first():
        return jsonify(error='Ya existe una cuenta con ese correo'), 400

    id_sucursal = datos.get('id_sucursal') or None
    if rol_nombre == 'cajero' and id_sucursal and db.session.get(Sucursal, id_sucursal) is None:
        return jsonify(error='Sede no encontrada'), 404

    rol = Rol.query.filter_by(nombre=rol_nombre).first()

    usuario = Usuario(
        nombre=nombre, apellido=apellido, correo=correo,
        contrasena=generate_password_hash(contrasena),
        estado=True, id_rol=rol.id_rol,
        id_sucursal=id_sucursal if rol_nombre == 'cajero' else None,
    )
    db.session.add(usuario)
    db.session.commit()
    return jsonify(_usuario_a_dict(usuario)), 201


@admin_bp.route('/api/admin/usuarios/<int:id_usuario>', methods=['PUT'])
@rol_requerido('administrador')
def editar_usuario(id_usuario):
    usuario = db.session.get(Usuario, id_usuario)
    if usuario is None:
        return jsonify(error='Usuario no encontrado'), 404

    datos = request.get_json(silent=True) or {}

    if 'nombre' in datos:
        nombre = (datos['nombre'] or '').strip()
        if not nombre:
            return jsonify(error='El nombre no puede estar vacío'), 400
        usuario.nombre = nombre

    if 'apellido' in datos:
        apellido = (datos['apellido'] or '').strip()
        if not apellido:
            return jsonify(error='El apellido no puede estar vacío'), 400
        usuario.apellido = apellido

    if 'correo' in datos:
        correo = (datos['correo'] or '').strip().lower()
        if not correo:
            return jsonify(error='El correo no puede estar vacío'), 400
        existente = Usuario.query.filter_by(correo=correo).first()
        if existente and existente.id_usuario != usuario.id_usuario:
            return jsonify(error='Ya existe una cuenta con ese correo'), 400
        usuario.correo = correo

    if 'id_sucursal' in datos and usuario.rol and usuario.rol.nombre == 'cajero':
        valor = datos['id_sucursal']
        try:
            id_sucursal = int(valor) if valor not in (None, '') else None
        except (TypeError, ValueError):
            return jsonify(error='id_sucursal no es válido'), 400

        if id_sucursal != usuario.id_sucursal:
            caja_abierta = Caja.query.filter_by(estado='abierta', id_usuario=usuario.id_usuario).first()
            if caja_abierta:
                sede_actual = db.session.get(Sucursal, usuario.id_sucursal) if usuario.id_sucursal else None
                nombre_sede = sede_actual.nombre if sede_actual else 'su sede actual'
                return jsonify(
                    error=f'Este cajero tiene la caja abierta en {nombre_sede}; debe cerrarla antes de cambiarlo de sede.'
                ), 409

        if id_sucursal and db.session.get(Sucursal, id_sucursal) is None:
            return jsonify(error='Sede no encontrada'), 404
        usuario.id_sucursal = id_sucursal

    db.session.commit()
    return jsonify(_usuario_a_dict(usuario))


@admin_bp.route('/api/admin/usuarios/<int:id_usuario>/estado', methods=['POST'])
@rol_requerido('administrador')
def cambiar_estado_usuario(id_usuario):
    if id_usuario == session.get('id_usuario'):
        return jsonify(error='No puedes desactivar tu propia cuenta'), 400

    usuario = db.session.get(Usuario, id_usuario)
    if usuario is None:
        return jsonify(error='Usuario no encontrado'), 404

    usuario.estado = not usuario.estado
    db.session.commit()
    return jsonify(_usuario_a_dict(usuario))


@admin_bp.route('/api/admin/usuarios/<int:id_usuario>/clave', methods=['POST'])
@rol_requerido('administrador')
def resetear_clave_usuario(id_usuario):
    usuario = db.session.get(Usuario, id_usuario)
    if usuario is None:
        return jsonify(error='Usuario no encontrado'), 404

    datos = request.get_json(silent=True) or {}
    nueva = datos.get('contrasena') or ''
    if len(nueva) < 8:
        return jsonify(error='La contraseña debe tener al menos 8 caracteres'), 400

    usuario.contrasena = generate_password_hash(nueva)
    db.session.commit()
    return jsonify(ok=True)


# ============================================================
# HORARIOS DE CAJEROS (turno laboral, no confundir con Turno de flota)
# ============================================================

def _turno_laboral_a_dict(t):
    return {
        'id_turno_laboral': t.id_turno_laboral,
        'nombre': t.nombre,
        'tipo': t.tipo,
        'hora_inicio': t.hora_inicio.strftime('%H:%M'),
        'hora_fin': t.hora_fin.strftime('%H:%M'),
        'estado': t.estado,
    }


@admin_bp.route('/api/admin/turnos-laborales')
@rol_requerido('administrador')
def listar_turnos_laborales():
    turnos = TurnoLaboral.query.order_by(TurnoLaboral.hora_inicio).all()
    return jsonify([_turno_laboral_a_dict(t) for t in turnos])


@admin_bp.route('/api/admin/turnos-laborales', methods=['POST'])
@rol_requerido('administrador')
def crear_turno_laboral():
    datos = request.get_json(silent=True) or {}
    nombre = (datos.get('nombre') or '').strip()

    if not nombre or not datos.get('hora_inicio') or not datos.get('hora_fin'):
        return jsonify(error='Indica nombre, hora_inicio y hora_fin'), 400
    if TurnoLaboral.query.filter_by(nombre=nombre).first():
        return jsonify(error='Ya existe un turno con ese nombre'), 400

    try:
        hora_inicio = datetime.strptime(datos['hora_inicio'], '%H:%M').time()
        hora_fin = datetime.strptime(datos['hora_fin'], '%H:%M').time()
    except ValueError:
        return jsonify(error='hora_inicio/hora_fin deben tener formato HH:MM'), 400

    turno = TurnoLaboral(
        nombre=nombre, tipo=datos.get('tipo', 'completo'),
        hora_inicio=hora_inicio, hora_fin=hora_fin,
    )
    db.session.add(turno)
    db.session.commit()
    return jsonify(_turno_laboral_a_dict(turno)), 201


def _lunes_de(fecha):
    return fecha - timedelta(days=fecha.weekday())


@admin_bp.route('/api/admin/horarios')
@rol_requerido('administrador')
def ver_horarios_semana():
    """?semana=AAAA-MM-DD (cualquier día de esa semana; por defecto hoy)."""
    semana = request.args.get('semana')
    try:
        referencia = datetime.strptime(semana, '%Y-%m-%d').date() if semana else date.today()
    except ValueError:
        return jsonify(error='semana debe tener el formato AAAA-MM-DD'), 400

    lunes = _lunes_de(referencia)
    dias = [lunes + timedelta(days=i) for i in range(7)]

    cajeros = (
        Usuario.query.join(Rol)
        .filter(Rol.nombre == 'cajero', Usuario.estado.is_(True))
        .order_by(Usuario.nombre).all()
    )

    asignaciones = (
        AsignacionTurno.query
        .filter(AsignacionTurno.fecha >= lunes, AsignacionTurno.fecha <= dias[-1])
        .all()
    )
    mapa = {(a.id_usuario, a.fecha.isoformat()): a.id_turno_laboral for a in asignaciones}

    return jsonify({
        'lunes': lunes.isoformat(),
        'dias': [d.isoformat() for d in dias],
        'cajeros': [
            {'id_usuario': c.id_usuario, 'nombre': f'{c.nombre} {c.apellido}'}
            for c in cajeros
        ],
        'asignaciones': [
            {'id_usuario': id_u, 'fecha': fecha, 'id_turno_laboral': id_t}
            for (id_u, fecha), id_t in mapa.items()
        ],
    })


@admin_bp.route('/api/admin/horarios', methods=['POST'])
@rol_requerido('administrador')
def guardar_horarios_semana():
    """Body: {"asignaciones": [{"id_usuario":1,"fecha":"2026-01-05","id_turno_laboral":2}, ...]}
    Una fila con id_turno_laboral=null borra la asignación de ese día."""
    datos = request.get_json(silent=True) or {}
    asignaciones = datos.get('asignaciones') or []

    for item in asignaciones:
        try:
            id_usuario = int(item['id_usuario'])
            fecha = datetime.strptime(item['fecha'], '%Y-%m-%d').date()
        except (KeyError, ValueError, TypeError):
            return jsonify(error='Cada asignación necesita id_usuario y fecha válidos'), 400

        existente = AsignacionTurno.query.filter_by(id_usuario=id_usuario, fecha=fecha).first()

        if not item.get('id_turno_laboral'):
            if existente:
                db.session.delete(existente)
            continue

        if existente:
            existente.id_turno_laboral = item['id_turno_laboral']
        else:
            db.session.add(AsignacionTurno(
                id_usuario=id_usuario, fecha=fecha,
                id_turno_laboral=item['id_turno_laboral'],
            ))

    db.session.commit()
    return jsonify(ok=True)


@admin_bp.route('/api/admin/horarios/copiar-semana-anterior', methods=['POST'])
@rol_requerido('administrador')
def copiar_semana_anterior():
    datos = request.get_json(silent=True) or {}
    try:
        referencia = datetime.strptime(datos.get('semana'), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return jsonify(error='Indica semana=AAAA-MM-DD'), 400

    lunes_actual = _lunes_de(referencia)
    lunes_anterior = lunes_actual - timedelta(days=7)

    previas = AsignacionTurno.query.filter(
        AsignacionTurno.fecha >= lunes_anterior,
        AsignacionTurno.fecha < lunes_actual,
    ).all()

    copiadas = 0
    for a in previas:
        nueva_fecha = a.fecha + timedelta(days=7)
        if AsignacionTurno.query.filter_by(id_usuario=a.id_usuario, fecha=nueva_fecha).first():
            continue
        db.session.add(AsignacionTurno(
            id_usuario=a.id_usuario, fecha=nueva_fecha,
            id_turno_laboral=a.id_turno_laboral,
        ))
        copiadas += 1

    db.session.commit()
    return jsonify(copiadas=copiadas)
