"""Los 98 casos de la hoja 'Casos de prueba' de Casos_de_Prueba_DinoPark.xlsx.

Cada función recibe:
- ctx: navegadores con sesión (ctx.cliente('ana')), ctx.api(), ctx.sql()…
- r:   donde se anotan las verificaciones (r.ver, r.http, r.mensaje…)

Los IDs esperados (usuarios, reservas, turnos…) asumen la BD limpia y el orden
de la columna 'Orden', igual que en el Excel. La fecha de los turnos y el
prefijo de los tickets se toman del día en que se ejecutan las pruebas.
"""
import os
import re
from datetime import datetime

from app.pruebas.motor import caso

# ------------------------------------------------------------ datos de prueba
ANA = ('ana.torres@correo.com', 'Dino2026!')
CARLOS = ('carlos.ruiz@correo.com', 'Carlos2026!')
CAJERO = ('cajero@dinopark.pe', 'Cajero2026!')
ADMIN = ('admin.dino@correo.com', 'Admin2026!')

SIN_PERMISO = {'error': 'No tienes permiso para esta acción'}
CREDENCIALES_MAL = 'Correo/DNI o contraseña incorrectos.'

# Archivos de prueba (solo importa su contenido, no una captura real)
PNG = b'\x89PNG\r\n\x1a\n'
JPG = b'\xff\xd8\xff\xe0'
YAPE_RESERVA1 = PNG + b'captura yape reserva 1 - S/ 15.00'
YAPE_RESERVA2 = JPG + b'captura yape reserva 2 - S/ 20.00'
YAPE_EXTRA = PNG + b'captura yape extra'
BOLETA_PDF = b'%PDF-1.4\n% boleta de prueba\n'
NOTAS_TXT = b'pago'
FOTO_8MB = JPG + bytes(8 * 1024 * 1024)

HORARIOS = ['10:00–10:20', '10:30–10:50', '11:00–11:20',
            '11:30–11:50', '12:00–12:20', '12:30–12:50']


def _registro(**cambios):
    """Formulario de /registro con los datos de María León.
    Un valor None deja el campo sin enviar (casilla sin marcar)."""
    datos = {
        'nombres': 'María', 'apellidos': 'León Castro', 'dni': '74567890',
        'telefono': '998877665',
        'correo': 'maria.leon@correo.com',
        'contrasena': 'Maria2026!', 'confirmar_contrasena': 'Maria2026!',
        'terminos': 'on', 'declaracion': 'on',
    }
    datos.update(cambios)
    return {k: v for k, v in datos.items() if v is not None}


def _registro_de(nombres, apellidos, dni, telefono, correo, contrasena):
    return _registro(nombres=nombres, apellidos=apellidos, dni=dni, telefono=telefono,
                     correo=correo,
                     contrasena=contrasena, confirmar_contrasena=contrasena)


def _usuarios_maria(ctx):
    return ctx.valor("SELECT count(*) FROM usuarios WHERE correo LIKE 'maria.leon%'")


def _franja(turno):
    return f"{turno['horario_inicio'][11:16]}–{turno['horario_fin'][11:16]}"


def _estado_turno(ctx, id_turno):
    return ctx.valor('SELECT estado FROM turnos WHERE id_turno = :t', t=id_turno)


def _estado_reserva(ctx, id_reserva):
    return ctx.valor('SELECT estado FROM reservas WHERE id_reserva = :r', r=id_reserva)


def _estado_flota(ctx, id_flota):
    return ctx.valor('SELECT estado FROM flota WHERE id_flota = :f', f=id_flota)


def _turnos(ctx, id_flota):
    return ctx.nuevo_cliente().get(
        f'/api/turnos?fecha={ctx.fecha}&id_flota={id_flota}').get_json()


def _registro_caso_invalido(ctx, r, datos, mensaje):
    resp = ctx.nuevo_cliente().post('/registro', data=datos)
    r.ver('HTTP', resp.status_code, 400)
    r.mensaje(resp, mensaje)
    r.ver('Usuarios maria.leon* en BD', _usuarios_maria(ctx), 0)


def _login_fallido(ctx, r, identificador, contrasena):
    cliente = ctx.nuevo_cliente()
    resp = ctx.login(cliente, identificador, contrasena)
    r.ver('HTTP', resp.status_code, 401)
    r.mensaje(resp, CREDENCIALES_MAL)
    with cliente.session_transaction() as sesion:
        r.ver('Sesión iniciada', 'id_usuario' in sesion, False)


# =====================================================================
# HU01 – Inicio de sesión y control de acceso
# =====================================================================
@caso('CP-01-01', 1, 'HU01', 'Registrar a la cliente Ana Torres',
      'Mensaje "¡Cuenta creada! Ya puedes iniciar sesión.", redirige a /iniciar-sesion. '
      'BD: usuario (2, rol 3, activo) y cliente id 1')
def cp_01_01(ctx, r):
    cliente = ctx.nuevo_cliente()
    resp = cliente.post('/registro', data=_registro_de(
        'Ana Lucía', 'Torres Vega', '71234567', '987654321', *ANA))
    r.redirige(resp, '/iniciar-sesion')
    r.mensaje(cliente.get('/iniciar-sesion'), '¡Cuenta creada! Ya puedes iniciar sesión.')
    fila = ctx.sql('SELECT id_usuario, id_rol, estado FROM usuarios WHERE correo = :c', c=ANA[0])
    r.ver('BD usuarios (id_usuario, id_rol, estado)', tuple(fila[0]) if fila else None, (2, 3, True))
    r.ver('BD clientes id_cliente',
          ctx.valor("SELECT id_cliente FROM clientes WHERE dni = '71234567'"), 1)


@caso('CP-01-02', 2, 'HU01', 'Registrar al cliente Carlos Ruiz',
      'Mensaje de cuenta creada. BD: usuario id 3, cliente id 2')
def cp_01_02(ctx, r):
    resp = ctx.nuevo_cliente().post('/registro', data=_registro_de(
        'Carlos', 'Ruiz Mendoza', '72345678', '912345678', *CARLOS))
    r.redirige(resp, '/iniciar-sesion')
    r.ver('BD id_usuario', ctx.valor('SELECT id_usuario FROM usuarios WHERE correo = :c', c=CARLOS[0]), 3)
    r.ver('BD id_cliente', ctx.valor("SELECT id_cliente FROM clientes WHERE dni = '72345678'"), 2)


@caso('CP-01-03', 3, 'HU01', 'Registrar la cuenta que será administrador',
      'Registro OK (usuario id 4), UPDATE 1, rol = administrador')
def cp_01_03(ctx, r):
    resp = ctx.nuevo_cliente().post('/registro', data=_registro_de(
        'Rosa', 'Quispe Díaz', '70000001', '976000001', *ADMIN))
    r.redirige(resp, '/iniciar-sesion')
    r.ver('UPDATE', ctx.sql('UPDATE usuarios SET id_rol = 1 WHERE correo = :c', c=ADMIN[0]), 1)
    r.ver('BD id_usuario', ctx.valor('SELECT id_usuario FROM usuarios WHERE correo = :c', c=ADMIN[0]), 4)
    r.ver('BD rol', ctx.valor(
        'SELECT r.nombre FROM usuarios u JOIN roles r ON r.id_rol = u.id_rol '
        'WHERE u.correo = :c', c=ADMIN[0]), 'administrador')


@caso('CP-01-04', 4, 'HU01', 'Registrar y desactivar a Luis Paredes',
      'Registro OK (usuario id 5), UPDATE 1, estado = false')
def cp_01_04(ctx, r):
    correo = 'luis.inactivo@correo.com'
    resp = ctx.nuevo_cliente().post('/registro', data=_registro_de(
        'Luis', 'Paredes Soto', '73456789', '965432187', correo, 'Luis2026!'))
    r.redirige(resp, '/iniciar-sesion')
    r.ver('UPDATE', ctx.sql('UPDATE usuarios SET estado = false WHERE correo = :c', c=correo), 1)
    fila = ctx.sql('SELECT id_usuario, estado FROM usuarios WHERE correo = :c', c=correo)
    r.ver('BD (id_usuario, estado)', tuple(fila[0]) if fila else None, (5, False))


@caso('CP-01-06', 6, 'HU01', 'Contraseña y confirmación no coinciden',
      'HTTP 400, "Las contraseñas no coinciden.", no se crea el usuario')
def cp_01_06(ctx, r):
    _registro_caso_invalido(ctx, r, _registro(confirmar_contrasena='Maria2025!'),
                            'Las contraseñas no coinciden.')


@caso('CP-01-07', 7, 'HU01', 'Contraseña de 7 caracteres',
      'HTTP 400, "La contraseña debe tener al menos 8 caracteres."')
def cp_01_07(ctx, r):
    _registro_caso_invalido(ctx, r, _registro(contrasena='Dino202', confirmar_contrasena='Dino202'),
                            'La contraseña debe tener al menos 8 caracteres.')


@caso('CP-01-08', 8, 'HU01', 'Registro sin aceptar términos',
      'HTTP 400, "Debes aceptar los términos y la declaración."')
def cp_01_08(ctx, r):
    _registro_caso_invalido(ctx, r, _registro(terminos=None),
                            'Debes aceptar los términos y la declaración.')


@caso('CP-01-09', 9, 'HU01', 'Registro con teléfono vacío',
      'HTTP 400, "Completa todos los campos obligatorios."')
def cp_01_09(ctx, r):
    _registro_caso_invalido(ctx, r, _registro(telefono=''),
                            'Completa todos los campos obligatorios.')


@caso('CP-01-10', 10, 'HU01', 'Registro con correo ya existente',
      'HTTP 400, "Ya existe una cuenta con ese correo.", sigue 1 usuario con ese correo')
def cp_01_10(ctx, r):
    resp = ctx.nuevo_cliente().post('/registro', data=_registro_de(
        'Ana', 'Torres', '75678901', '944556677', ANA[0], 'Otra2026!'))
    r.ver('HTTP', resp.status_code, 400)
    r.mensaje(resp, 'Ya existe una cuenta con ese correo.')
    r.ver('Usuarios con ese correo', ctx.valor(
        'SELECT count(*) FROM usuarios WHERE correo = :c', c=ANA[0]), 1)


@caso('CP-01-11', 11, 'HU01', 'Registro con DNI ya existente',
      'HTTP 400, "Ya existe una cuenta con ese documento.", no se crea pedro.gomez')
def cp_01_11(ctx, r):
    resp = ctx.nuevo_cliente().post('/registro', data=_registro_de(
        'Pedro', 'Gómez Ríos', '71234567', '955443322', 'pedro.gomez@correo.com', 'Pedro2026!'))
    r.ver('HTTP', resp.status_code, 400)
    r.mensaje(resp, 'Ya existe una cuenta con ese documento.')
    r.ver('Usuarios pedro.gomez', ctx.valor(
        "SELECT count(*) FROM usuarios WHERE correo = 'pedro.gomez@correo.com'"), 0)


@caso('CP-01-12', 12, 'HU01', 'Cliente inicia sesión con su correo',
      'Redirige a /disponibilidad con el título "Reserva de Turnos & Atracciones"')
def cp_01_12(ctx, r):
    ana = ctx.cliente('ana')
    r.redirige(ctx.login(ana, *ANA), '/disponibilidad')
    pagina = ana.get('/disponibilidad')
    r.ver('HTTP /disponibilidad', pagina.status_code, 200)
    r.mensaje(pagina, 'Reserva de Turnos & Atracciones')


@caso('CP-01-13', 13, 'HU01', 'Correo escrito en mayúsculas',
      'Inicia sesión y redirige a /disponibilidad')
def cp_01_13(ctx, r):
    r.redirige(ctx.login(ctx.nuevo_cliente(), ANA[0].upper(), ANA[1]), '/disponibilidad')


@caso('CP-01-14', 14, 'HU01', 'Cliente inicia sesión con su DNI',
      'Inicia sesión como Ana Lucía y redirige a /disponibilidad')
def cp_01_14(ctx, r):
    cliente = ctx.nuevo_cliente()
    r.redirige(ctx.login(cliente, '71234567', ANA[1]), '/disponibilidad')
    with cliente.session_transaction() as sesion:
        r.ver('Sesión como', sesion.get('nombre'), 'Ana Lucía')


@caso('CP-01-15', 15, 'HU01', 'Cajero inicia sesión',
      'Redirige a /caja/validaciones ("Validación de pagos Yape"), sin reservas por validar')
def cp_01_15(ctx, r):
    cajero = ctx.cliente('cajero')
    r.redirige(ctx.login(cajero, *CAJERO), '/caja/validaciones')
    r.mensaje(cajero.get('/caja/validaciones'), 'Validación de pagos Yape')
    r.ver('Reservas por validar', cajero.get('/api/caja/reservas').get_json(), [])


@caso('CP-01-16', 16, 'HU01', 'Administrador inicia sesión',
      'Inicia sesión y redirige a la página de inicio "/"')
def cp_01_16(ctx, r):
    r.redirige(ctx.login(ctx.cliente('admin'), *ADMIN), '/')


@caso('CP-01-17', 17, 'HU01', "Sesión persistente con 'Recordarme'",
      'Cookie de sesión válida ~30 días; al reabrir el navegador entra a /disponibilidad sin login')
def cp_01_17(ctx, r):
    carlos = ctx.cliente('carlos')
    r.redirige(ctx.login(carlos, *CARLOS, recordarme=True), '/disponibilidad')
    cookie = carlos.get_cookie('session')
    dias = None
    if cookie is not None and cookie.expires is not None:
        vence = cookie.expires.replace(tzinfo=None)
        dias = (vence - datetime.utcnow()).days
    r.cumple('Cookie persistente (días de vigencia)', dias is not None and 29 <= dias <= 30,
             dias, '29–30')
    navegador_nuevo = ctx.nuevo_cliente()
    if cookie is not None:
        navegador_nuevo.set_cookie('session', cookie.value)
    r.ver('Navegador nuevo → /disponibilidad (HTTP)',
          navegador_nuevo.get('/disponibilidad').status_code, 200)


@caso('CP-01-18', 18, 'HU01', 'Contraseña incorrecta',
      'HTTP 401, "Correo/DNI o contraseña incorrectos."')
def cp_01_18(ctx, r):
    _login_fallido(ctx, r, ANA[0], 'Dino2025!')


@caso('CP-01-19', 19, 'HU01', 'Correo no registrado',
      'HTTP 401, "Correo/DNI o contraseña incorrectos."')
def cp_01_19(ctx, r):
    _login_fallido(ctx, r, 'jorge.vargas@correo.com', 'Dino2026!')


@caso('CP-01-20', 20, 'HU01', 'DNI no registrado',
      'HTTP 401, "Correo/DNI o contraseña incorrectos."')
def cp_01_20(ctx, r):
    _login_fallido(ctx, r, '99999999', 'Dino2026!')


@caso('CP-01-21', 21, 'HU01', 'Contraseña vacía',
      'HTTP 401, "Correo/DNI o contraseña incorrectos." No inicia sesión')
def cp_01_21(ctx, r):
    _login_fallido(ctx, r, ANA[0], '')


@caso('CP-01-22', 22, 'HU01', 'Usuario desactivado con contraseña correcta',
      'HTTP 401, "Correo/DNI o contraseña incorrectos." No inicia sesión')
def cp_01_22(ctx, r):
    _login_fallido(ctx, r, 'luis.inactivo@correo.com', 'Luis2026!')


@caso('CP-01-23', 23, 'HU01', 'Cliente abre el panel de caja',
      'HTTP 403 {"error": "No tienes permiso para esta acción"}')
def cp_01_23(ctx, r):
    r.http(ctx.cliente('ana').get('/caja/validaciones'), 403, SIN_PERMISO)


@caso('CP-01-24', 24, 'HU01', 'Abrir /disponibilidad sin sesión',
      'Redirige a /iniciar-sesion')
def cp_01_24(ctx, r):
    r.redirige(ctx.nuevo_cliente().get('/disponibilidad'), '/iniciar-sesion')


@caso('CP-01-25', 25, 'HU01', 'Llamar a la API de reservas sin sesión',
      'HTTP 401 {"error": "Debes iniciar sesión"}')
def cp_01_25(ctx, r):
    r.http(ctx.nuevo_cliente().get('/api/reservas/mis'), 401, {'error': 'Debes iniciar sesión'})


@caso('CP-01-26', 26, 'HU01', 'Cliente intenta abrir caja por API',
      'HTTP 403 sin permiso. Cajas en BD: 0')
def cp_01_26(ctx, r):
    r.http(ctx.api(ctx.cliente('ana'), '/api/caja/abrir', {'monto_inicial': 100}), 403, SIN_PERMISO)
    r.ver('Cajas en BD', ctx.valor('SELECT count(*) FROM cajas'), 0)


@caso('CP-01-27', 27, 'HU01', 'Cajero intenta registrar un mantenimiento',
      'HTTP 403 sin permiso. Mantenimientos en BD: 0')
def cp_01_27(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/mantenimientos',
                   {'id_flota': 1, 'tipo': 'preventivo'}), 403, SIN_PERMISO)
    r.ver('Mantenimientos en BD', ctx.valor('SELECT count(*) FROM mantenimientos'), 0)


@caso('CP-01-28', 28, 'HU01', 'Cerrar sesión',
      'Cerrar sesión redirige a "/"; luego /disponibilidad redirige a /iniciar-sesion')
def cp_01_28(ctx, r):
    cliente = ctx.nuevo_cliente()
    ctx.login(cliente, *ANA)
    r.redirige(cliente.get('/cerrar-sesion'), '/')
    r.redirige(cliente.get('/disponibilidad'), '/iniciar-sesion')


# =====================================================================
# HU02 – Consulta de disponibilidad y reserva de turnos
# =====================================================================
@caso('CP-02-01', 29, 'HU02', 'Listar sedes activas',
      'id 1 Real Plaza, id 2 Mega Plaza e id 3 Hoyos Rubio con sus direcciones')
def cp_02_01(ctx, r):
    r.http(ctx.nuevo_cliente().get('/api/sedes'), 200, [
        {'id_sucursal': 1, 'nombre': 'Real Plaza',
         'direccion': 'Real Plaza Cajamarca (Nivel 2, Explanada Jurásica)'},
        {'id_sucursal': 2, 'nombre': 'Mega Plaza',
         'direccion': 'Mega Plaza Cajamarca (Primer Nivel, Zona Recreativa Central)'},
        {'id_sucursal': 3, 'nombre': 'Hoyos Rubio',
         'direccion': 'Jr. Hoyos Rubio (Cajamarca)'},
    ])


@caso('CP-02-02', 30, 'HU02', 'Flota de la sede Real Plaza',
      '5 unidades (ids 1–5) disponibles, ninguna de la sede 2')
def cp_02_02(ctx, r):
    flota = ctx.nuevo_cliente().get('/api/flota?id_sucursal=1').get_json()
    r.ver('Unidades', [[f['id_flota'], f['nombre'], f['tipo'], f['precio_hora'], f['estado']]
                       for f in flota], [
        [1, 'Dino Rider #01 (T-Rex Rexy)', 'dinosaurio', 15.0, 'disponible'],
        [2, 'Dino Rider #02 (T-Rex Spiky)', 'dinosaurio', 15.0, 'disponible'],
        [3, 'Super Carro Rojo AMG #04', 'carro', 20.0, 'disponible'],
        [4, 'Moto GP Dino Ninja #07', 'moto', 15.0, 'disponible'],
        [5, 'Moto GP Dino Ninja #08', 'moto', 15.0, 'disponible'],
    ])


@caso('CP-02-03', 31, 'HU02', "Filtrar flota por tipo 'moto'",
      '3 motos: id 4 y 5 (sede 1), id 8 (sede 2)')
def cp_02_03(ctx, r):
    motos = ctx.nuevo_cliente().get('/api/flota?tipo=moto').get_json()
    r.ver('Motos', [[m['id_flota'], m['nombre'], m['id_sucursal']] for m in motos], [
        [4, 'Moto GP Dino Ninja #07', 1],
        [5, 'Moto GP Dino Ninja #08', 1],
        [8, 'Moto GP Dino Ninja #09', 2],
    ])


@caso('CP-02-04', 32, 'HU02', 'Turnos de Dino Rider #01',
      '6 turnos (id 1–6) de hoy, 10:00 a 12:50, capacidad 1')
def cp_02_04(ctx, r):
    turnos = _turnos(ctx, 1)
    r.ver('Turnos (id, franja, capacidad)',
          [[t['id_turno'], _franja(t), t['capacidad']] for t in turnos],
          [[i + 1, h, 1] for i, h in enumerate(HORARIOS)])
    r.ver('Fecha de los turnos', sorted({t['horario_inicio'][:10] for t in turnos}), [ctx.fecha])


@caso('CP-02-05', 33, 'HU02', 'Fecha con formato DD-MM-AAAA',
      'HTTP 400 {"error": "La fecha debe tener el formato AAAA-MM-DD"}')
def cp_02_05(ctx, r):
    r.http(ctx.nuevo_cliente().get(f'/api/turnos?fecha={ctx.hoy:%d-%m-%Y}'), 400,
           {'error': 'La fecha debe tener el formato AAAA-MM-DD'})


@caso('CP-02-06', 34, 'HU02', 'Fecha sin turnos programados',
      'HTTP 200 con lista vacía []')
def cp_02_06(ctx, r):
    fecha = '2026-12-25' if ctx.fecha != '2026-12-25' else '2026-12-26'
    r.http(ctx.nuevo_cliente().get(f'/api/turnos?fecha={fecha}'), 200, [])


@caso('CP-02-07', 35, 'HU02', 'Ana reserva Dino Rider #01 a las 10:00',
      'HTTP 201: reserva 1 pendiente, 1 persona, total 15.0; número Yape 972 751 444 visible; turno 1 lleno')
def cp_02_07(ctx, r):
    ana = ctx.cliente('ana')
    resp = ctx.api(ana, '/api/reservas', {'cantidad_personas': 1, 'items': [{'id_flota': 1, 'id_turno': 1}]})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Reserva', resp.get_json(), {
        'id_reserva': 1, 'estado': 'pendiente', 'cantidad_personas': 1, 'total': 15.0,
        'detalles': [{'id_flota': 1, 'flota': 'Dino Rider #01 (T-Rex Rexy)', 'id_turno': 1}],
    })
    r.mensaje(ana.get('/disponibilidad'), '972 751 444')
    r.ver('BD turno 1', _estado_turno(ctx, 1), 'lleno')


@caso('CP-02-08', 36, 'HU02', 'Ana reserva 2 atracciones en una sola reserva',
      'HTTP 201: reserva 2 pendiente, 2 personas, total 35.0, turnos 2 y 19 llenos')
def cp_02_08(ctx, r):
    resp = ctx.api(ctx.cliente('ana'), '/api/reservas', {'cantidad_personas': 2, 'items': [
        {'id_flota': 1, 'id_turno': 2}, {'id_flota': 3, 'id_turno': 19}]})
    r.ver('HTTP', resp.status_code, 201)
    datos = resp.get_json() or {}
    r.campos('Reserva', datos, {'id_reserva': 2, 'estado': 'pendiente',
                                'cantidad_personas': 2, 'total': 35.0})
    r.ver('Turnos de los detalles', [d['id_turno'] for d in datos.get('detalles', [])], [2, 19])
    r.ver('BD turnos 2 y 19', [_estado_turno(ctx, 2), _estado_turno(ctx, 19)], ['lleno', 'lleno'])


@caso('CP-02-09', 37, 'HU02', 'Carlos reserva Moto GP Dino Ninja #07',
      'HTTP 201: reserva 3, total 15.0, pendiente. Turno 31 lleno')
def cp_02_09(ctx, r):
    resp = ctx.api(ctx.cliente('carlos'), '/api/reservas',
                   {'cantidad_personas': 1, 'items': [{'id_flota': 4, 'id_turno': 31}]})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Reserva', resp.get_json(), {'id_reserva': 3, 'total': 15.0, 'estado': 'pendiente'})
    r.ver('BD turno 31', _estado_turno(ctx, 31), 'lleno')


@caso('CP-02-10', 38, 'HU02', 'Carlos reserva Moto GP Dino Ninja #08',
      'HTTP 201: reserva 4, total 15.0, pendiente. Turno 37 lleno')
def cp_02_10(ctx, r):
    resp = ctx.api(ctx.cliente('carlos'), '/api/reservas',
                   {'cantidad_personas': 1, 'items': [{'id_flota': 5, 'id_turno': 37}]})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Reserva', resp.get_json(), {'id_reserva': 4, 'total': 15.0, 'estado': 'pendiente'})
    r.ver('BD turno 37', _estado_turno(ctx, 37), 'lleno')


@caso('CP-02-11', 39, 'HU02', 'Carlos intenta reservar el turno que ya tomó Ana',
      'El turno 10:00 no aparece; HTTP 400 "no está disponible en ese turno"; 1 detalle en turno 1')
def cp_02_11(ctx, r):
    ids = [t['id_turno'] for t in _turnos(ctx, 1)]
    r.ver('Turno 1 visible en disponibilidad', 1 in ids, False)
    r.http(ctx.api(ctx.cliente('carlos'), '/api/reservas',
                   {'cantidad_personas': 1, 'items': [{'id_flota': 1, 'id_turno': 1}]}),
           400, {'error': 'Dino Rider #01 (T-Rex Rexy) no está disponible en ese turno'})
    r.ver('Detalles en turno 1', ctx.valor(
        'SELECT count(*) FROM detalles_reserva WHERE id_turno = 1'), 1)


@caso('CP-02-12', 40, 'HU02', 'Turno que pertenece a otra unidad',
      'HTTP 400 {"error": "El turno no corresponde a esa atracción"}')
def cp_02_12(ctx, r):
    r.http(ctx.api(ctx.cliente('carlos'), '/api/reservas', {'items': [{'id_flota': 1, 'id_turno': 7}]}),
           400, {'error': 'El turno no corresponde a esa atracción'})


@caso('CP-02-13', 41, 'HU02', 'Reserva sin atracciones',
      'HTTP 400 {"error": "Debes indicar al menos una atracción y un turno"}')
def cp_02_13(ctx, r):
    r.http(ctx.api(ctx.cliente('carlos'), '/api/reservas', {'cantidad_personas': 1, 'items': []}),
           400, {'error': 'Debes indicar al menos una atracción y un turno'})


@caso('CP-02-14', 42, 'HU02', 'Reserva con 0 personas',
      'HTTP 400 "La cantidad de personas debe ser como mínimo 1"; turno 3 sigue disponible')
def cp_02_14(ctx, r):
    r.http(ctx.api(ctx.cliente('carlos'), '/api/reservas',
                   {'cantidad_personas': 0, 'items': [{'id_flota': 1, 'id_turno': 3}]}),
           400, {'error': 'La cantidad de personas debe ser como mínimo 1'})
    r.ver('BD turno 3', _estado_turno(ctx, 3), 'disponible')


@caso('CP-02-15', 43, 'HU02', 'Atracción y turno inexistentes',
      'HTTP 400 {"error": "La atracción o el turno no existe"}')
def cp_02_15(ctx, r):
    r.http(ctx.api(ctx.cliente('carlos'), '/api/reservas', {'items': [{'id_flota': 999, 'id_turno': 999}]}),
           400, {'error': 'La atracción o el turno no existe'})


@caso('CP-02-16', 44, 'HU02', 'Carlos intenta ver la reserva de Ana',
      'HTTP 404 {"error": "Reserva no encontrada"}')
def cp_02_16(ctx, r):
    r.http(ctx.cliente('carlos').get('/api/reservas/1'), 404, {'error': 'Reserva no encontrada'})


@caso('CP-02-17', 45, 'HU02', 'Carlos cancela la reserva 4',
      'Reserva 4 cancelada; turno 37 disponible; 6 turnos disponibles para la unidad 5')
def cp_02_17(ctx, r):
    resp = ctx.api(ctx.cliente('carlos'), '/api/reservas/4/cancelar', {})
    r.ver('HTTP', resp.status_code, 200)
    r.campos('Reserva', resp.get_json(), {'id_reserva': 4, 'estado': 'cancelada'})
    r.ver('BD turno 37', _estado_turno(ctx, 37), 'disponible')
    r.ver('Turnos disponibles unidad 5', len(_turnos(ctx, 5)), 6)


@caso('CP-02-18', 46, 'HU02', 'Cancelar otra vez una reserva cancelada',
      'HTTP 400 {"error": "La reserva ya estaba cancelada"}')
def cp_02_18(ctx, r):
    r.http(ctx.api(ctx.cliente('carlos'), '/api/reservas/4/cancelar', {}),
           400, {'error': 'La reserva ya estaba cancelada'})


@caso('CP-02-19', 47, 'HU02', 'Duración y horario de los turnos de Dino Rider #05',
      '6 turnos (id 13 a 18) de 10:00 a 12:50; cada turno dura 20 minutos')
def cp_02_19(ctx, r):
    turnos = _turnos(ctx, 6)
    r.ver('Turnos (id, franja)', [[t['id_turno'], _franja(t)] for t in turnos],
          [[13 + i, h] for i, h in enumerate(HORARIOS)])
    duraciones = sorted({
        int((datetime.fromisoformat(t['horario_fin'])
             - datetime.fromisoformat(t['horario_inicio'])).total_seconds() // 60)
        for t in turnos})
    r.ver('Duración de cada turno (minutos)', duraciones, [20])


# =====================================================================
# HU03 – Registro de pago y generación de ticket
# =====================================================================
@caso('CP-03-01', 48, 'HU03', 'Ana sube la captura Yape de la reserva 1',
      'HTTP 201, reserva 1 por_validar, comprobante 1 (yape, por_validar, 15.0), archivo guardado')
def cp_03_01(ctx, r):
    resp = ctx.subir(ctx.cliente('ana'), 1, YAPE_RESERVA1, 'yape_reserva1.png')
    r.ver('HTTP', resp.status_code, 201)
    datos = resp.get_json() or {}
    r.ver('Reserva 1', datos.get('estado'), 'por_validar')
    r.campos('Comprobante', datos.get('comprobante'),
             {'id_comprobante': 1, 'estado': 'por_validar', 'monto': 15.0})
    fila = ctx.sql('SELECT metodo_pago, estado, archivo FROM comprobantes_reserva WHERE id_reserva = 1')
    r.ver('BD (metodo_pago, estado)', tuple(fila[0][:2]) if fila else None, ('yape', 'por_validar'))
    archivo = fila[0][2] if fila else ''
    guardado = bool(re.fullmatch(r'reserva1_[0-9a-f]{32}\.png', archivo or '')) and \
        os.path.isfile(os.path.join(ctx.carpeta, archivo))
    r.cumple('Archivo guardado', guardado, archivo, 'reserva1_<código>.png (existe)')


@caso('CP-03-02', 49, 'HU03', 'Reusar la captura de la reserva 1 en la reserva 2',
      'HTTP 400 "Esta captura ya fue usada en otra reserva"; reserva 2 sigue pendiente')
def cp_03_02(ctx, r):
    r.http(ctx.subir(ctx.cliente('ana'), 2, YAPE_RESERVA1, 'yape_reserva1.png'),
           400, {'error': 'Esta captura ya fue usada en otra reserva'})
    r.ver('BD reserva 2', _estado_reserva(ctx, 2), 'pendiente')


@caso('CP-03-03', 50, 'HU03', 'Subir un PDF como comprobante',
      'HTTP 400 "Sube una imagen PNG, JPG o WEBP"; reserva 2 sigue pendiente')
def cp_03_03(ctx, r):
    r.http(ctx.subir(ctx.cliente('ana'), 2, BOLETA_PDF, 'boleta.pdf'),
           400, {'error': 'Sube una imagen PNG, JPG o WEBP'})
    r.ver('BD reserva 2', _estado_reserva(ctx, 2), 'pendiente')


@caso('CP-03-04', 51, 'HU03', 'Archivo de texto renombrado a .png',
      'HTTP 400 "Sube una imagen PNG, JPG o WEBP" (se valida el contenido)')
def cp_03_04(ctx, r):
    r.http(ctx.subir(ctx.cliente('ana'), 2, NOTAS_TXT, 'notas.png'),
           400, {'error': 'Sube una imagen PNG, JPG o WEBP'})


@caso('CP-03-05', 52, 'HU03', 'Imagen de 8 MB',
      'HTTP 413 "La imagen supera los 5 MB"; reserva 2 sigue pendiente')
def cp_03_05(ctx, r):
    r.http(ctx.subir(ctx.cliente('ana'), 2, FOTO_8MB, 'foto_8mb.jpg'),
           413, {'error': 'La imagen supera los 5 MB'})
    r.ver('BD reserva 2', _estado_reserva(ctx, 2), 'pendiente')


@caso('CP-03-06', 53, 'HU03', 'Enviar sin seleccionar archivo',
      'HTTP 400 {"error": "Selecciona la captura de tu pago"}')
def cp_03_06(ctx, r):
    resp = ctx.cliente('ana').post('/api/reservas/2/comprobante', data={},
                                   content_type='multipart/form-data')
    r.http(resp, 400, {'error': 'Selecciona la captura de tu pago'})


@caso('CP-03-07', 54, 'HU03', 'Ana sube la captura de la reserva 2',
      'HTTP 201, reserva 2 por_validar, comprobante 2 con monto 35.0')
def cp_03_07(ctx, r):
    resp = ctx.subir(ctx.cliente('ana'), 2, YAPE_RESERVA2, 'yape_reserva2.jpg')
    r.ver('HTTP', resp.status_code, 201)
    datos = resp.get_json() or {}
    r.ver('Reserva 2', datos.get('estado'), 'por_validar')
    r.campos('Comprobante', datos.get('comprobante'), {'id_comprobante': 2, 'monto': 35.0})


@caso('CP-03-08', 55, 'HU03', 'Subir otra captura mientras la anterior se revisa',
      'HTTP 400 "Ya enviaste un comprobante, el cajero lo está revisando"')
def cp_03_08(ctx, r):
    r.http(ctx.subir(ctx.cliente('ana'), 1, YAPE_EXTRA, 'yape_extra.png'),
           400, {'error': 'Ya enviaste un comprobante, el cajero lo está revisando'})


@caso('CP-03-09', 56, 'HU03', 'Carlos intenta ver el comprobante de Ana',
      'HTTP 404 {"error": "Comprobante no encontrado"}')
def cp_03_09(ctx, r):
    r.http(ctx.cliente('carlos').get('/comprobantes/1'), 404, {'error': 'Comprobante no encontrado'})


@caso('CP-03-10', 57, 'HU03', 'Cajero acepta el pago de la reserva 1',
      'Reserva 1 confirmada; comprobante aceptado por el validador 1; Ana la ve confirmada')
def cp_03_10(ctx, r):
    cajero = ctx.cliente('cajero')
    por_validar = cajero.get('/api/caja/reservas').get_json() or []
    reserva1 = next((x for x in por_validar if x['id_reserva'] == 1), None)
    r.ver('Por validar: reserva 1',
          [reserva1['cliente']['nombre'], reserva1['cliente']['dni'], reserva1['total']] if reserva1 else None,
          ['Ana Lucía Torres Vega', '71234567', 15.0])
    resp = ctx.api(cajero, '/api/reservas/1/aceptar', {})
    r.ver('Aceptar (HTTP)', resp.status_code, 200)
    r.ver('Reserva 1', (resp.get_json() or {}).get('estado'), 'confirmada')
    fila = ctx.sql('SELECT estado, id_validador, fecha_validacion FROM comprobantes_reserva '
                   'WHERE id_comprobante = 1')
    r.ver('BD comprobante (estado, validador, con fecha)',
          (fila[0][0], fila[0][1], fila[0][2] is not None) if fila else None, ('aceptado', 1, True))
    confirmadas = cajero.get('/api/caja/reservas?estado=confirmada').get_json() or []
    r.ver("Pestaña 'Confirmadas'", [x['id_reserva'] for x in confirmadas], [1])
    de_ana = ctx.cliente('ana').get('/api/mis-reservas').get_json() or []
    r.ver('Ana ve la reserva 1', next((x['estado'] for x in de_ana if x['id_reserva'] == 1), None),
          'confirmada')


@caso('CP-03-11', 58, 'HU03', 'Subir captura a una reserva ya confirmada',
      'HTTP 400 {"error": "Esta reserva ya está confirmada"}')
def cp_03_11(ctx, r):
    r.http(ctx.subir(ctx.cliente('ana'), 1, YAPE_EXTRA, 'yape_extra.png'),
           400, {'error': 'Esta reserva ya está confirmada'})


@caso('CP-03-12', 59, 'HU03', 'Rechazar sin escribir motivo',
      'HTTP 400 "Indica el motivo del rechazo"; reserva 2 sigue por_validar')
def cp_03_12(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/reservas/2/rechazar', {'motivo': ''}),
           400, {'error': 'Indica el motivo del rechazo'})
    r.ver('BD reserva 2', _estado_reserva(ctx, 2), 'por_validar')


@caso('CP-03-13', 60, 'HU03', 'Rechazar pago con monto incompleto',
      'Reserva 2 vuelve a pendiente; comprobante 2 rechazado con el motivo; Ana ve el motivo')
def cp_03_13(ctx, r):
    motivo = 'El monto no coincide: se pagó S/ 20.00 y el total es S/ 35.00'
    resp = ctx.api(ctx.cliente('cajero'), '/api/reservas/2/rechazar', {'motivo': motivo})
    r.ver('HTTP', resp.status_code, 200)
    r.ver('Reserva 2', (resp.get_json() or {}).get('estado'), 'pendiente')
    fila = ctx.sql('SELECT estado, motivo_rechazo FROM comprobantes_reserva WHERE id_comprobante = 2')
    r.ver('BD comprobante 2', tuple(fila[0]) if fila else None, ('rechazado', motivo))
    de_ana = ctx.cliente('ana').get('/api/mis-reservas').get_json() or []
    reserva2 = next((x for x in de_ana if x['id_reserva'] == 2), None)
    r.ver('Ana ve el motivo',
          (reserva2 or {}).get('comprobante', {}).get('motivo_rechazo') if reserva2 else None, motivo)


@caso('CP-03-14', 61, 'HU03', 'Subir captura a una reserva cancelada',
      'HTTP 400 {"error": "Esta reserva fue cancelada"}')
def cp_03_14(ctx, r):
    r.http(ctx.subir(ctx.cliente('carlos'), 4, PNG, 'yape_carlos.png'),
           400, {'error': 'Esta reserva fue cancelada'})


@caso('CP-03-15', 62, 'HU03', 'Aceptar una reserva sin comprobante',
      'HTTP 400 "Esta reserva no tiene un comprobante por validar"; reserva 3 sigue pendiente')
def cp_03_15(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/reservas/3/aceptar', {}),
           400, {'error': 'Esta reserva no tiene un comprobante por validar'})
    r.ver('BD reserva 3', _estado_reserva(ctx, 3), 'pendiente')


# =====================================================================
# HU07 – Arqueo y cierre de caja (apertura y movimientos)
# =====================================================================
@caso('CP-07-01', 63, 'HU07', 'Abrir caja con S/ 100.00',
      'HTTP 201: caja 1 abierta, inicial 100.0, ingresos 0.0, egresos 0.0, saldo 100.0')
def cp_07_01(ctx, r):
    resp = ctx.api(ctx.cliente('cajero'), '/api/caja/abrir', {'monto_inicial': 100})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Caja', resp.get_json(), {
        'id_caja': 1, 'estado': 'abierta', 'monto_inicial': 100.0, 'ingresos': 0.0,
        'egresos': 0.0, 'saldo_actual': 100.0, 'monto_final': None, 'fecha_cierre': None})


@caso('CP-07-02', 64, 'HU07', 'Abrir una segunda caja',
      'HTTP 400 "Ya hay una caja abierta"; cajas en BD: 1')
def cp_07_02(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/caja/abrir', {'monto_inicial': 50}),
           400, {'error': 'Ya hay una caja abierta'})
    r.ver('Cajas en BD', ctx.valor('SELECT count(*) FROM cajas'), 1)


@caso('CP-07-03', 65, 'HU07', 'Registrar ingreso de S/ 50.00',
      'HTTP 201: ingresos 50.0, egresos 0.0, saldo 150.0')
def cp_07_03(ctx, r):
    resp = ctx.api(ctx.cliente('cajero'), '/api/caja/movimientos',
                   {'tipo': 'ingreso', 'monto': 50, 'descripcion': 'Venta de 10 globos de dinosaurio'})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Caja', resp.get_json(), {'ingresos': 50.0, 'egresos': 0.0, 'saldo_actual': 150.0})


@caso('CP-07-04', 66, 'HU07', 'Registrar egreso de S/ 20.00',
      'HTTP 201: ingresos 50.0, egresos 20.0, saldo 130.0 (100 + 50 − 20)')
def cp_07_04(ctx, r):
    resp = ctx.api(ctx.cliente('cajero'), '/api/caja/movimientos',
                   {'tipo': 'egreso', 'monto': 20, 'descripcion': 'Compra de 8 pilas AA'})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Caja', resp.get_json(), {'ingresos': 50.0, 'egresos': 20.0, 'saldo_actual': 130.0})


@caso('CP-07-05', 67, 'HU07', "Movimiento con tipo 'transferencia'",
      "HTTP 400 \"El tipo debe ser 'ingreso' o 'egreso'\"; saldo sigue en 130.0")
def cp_07_05(ctx, r):
    cajero = ctx.cliente('cajero')
    r.http(ctx.api(cajero, '/api/caja/movimientos', {'tipo': 'transferencia', 'monto': 30}),
           400, {'error': "El tipo debe ser 'ingreso' o 'egreso'"})
    r.ver('saldo_actual', (cajero.get('/api/caja/actual').get_json() or {}).get('saldo_actual'), 130.0)


@caso('CP-07-06', 68, 'HU07', 'Movimiento con monto 0',
      'HTTP 400 {"error": "El monto debe ser mayor a 0"}')
def cp_07_06(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/caja/movimientos', {'tipo': 'ingreso', 'monto': 0}),
           400, {'error': 'El monto debe ser mayor a 0'})


@caso('CP-07-07', 69, 'HU07', 'Movimiento con monto negativo',
      'HTTP 400 {"error": "El monto debe ser mayor a 0"}')
def cp_07_07(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/caja/movimientos', {'tipo': 'egreso', 'monto': -15.50}),
           400, {'error': 'El monto debe ser mayor a 0'})


@caso('CP-07-08', 70, 'HU07', 'Movimiento con monto de texto',
      'HTTP 400 {"error": "El monto debe ser mayor a 0"}')
def cp_07_08(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/caja/movimientos', {'tipo': 'ingreso', 'monto': 'cien'}),
           400, {'error': 'El monto debe ser mayor a 0'})


# =====================================================================
# HU04 – Venta presencial en taquilla
# =====================================================================
@caso('CP-04-01', 71, 'HU04', 'Venta de 2 dinosaurios y 1 carro',
      'HTTP 201: venta 1 pendiente, total 50.0, detalles 15×2=30 y 20×1=20 sin pagar')
def cp_04_01(ctx, r):
    resp = ctx.api(ctx.cliente('cajero'), '/api/ventas',
                   {'items': [{'precio': 15, 'cantidad': 2}, {'precio': 20, 'cantidad': 1}]})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Venta', resp.get_json(), {
        'id_venta': 1, 'estado': 'pendiente', 'total': 50.0, 'detalles': [
            {'id_detalle_venta': 1, 'precio': 15.0, 'cantidad': 2, 'subtotal': 30.0, 'pagado': False},
            {'id_detalle_venta': 2, 'precio': 20.0, 'cantidad': 1, 'subtotal': 20.0, 'pagado': False},
        ]})


@caso('CP-04-02', 72, 'HU04', 'Pagar la venta 1 en efectivo',
      'Venta 1 pagada, 2 tickets T<AAMMDD>-XXXXXX distintos; caja: ingresos 100.0, egresos 20.0, saldo 180.0')
def cp_04_02(ctx, r):
    cajero = ctx.cliente('cajero')
    resp = ctx.api(cajero, '/api/ventas/1/pago', {'metodo_pago': 'efectivo'})
    r.ver('HTTP', resp.status_code, 200)
    datos = resp.get_json() or {}
    r.ver('Venta 1', datos.get('estado'), 'pagada')
    r.ver('Detalles pagados', [d['pagado'] for d in datos.get('detalles', [])], [True, True])
    tickets = datos.get('tickets', [])
    formato = re.compile(re.escape(ctx.prefijo_ticket) + r'[0-9A-F]{6}')
    r.cumple('Tickets', len(set(tickets)) == 2 and all(formato.fullmatch(t) for t in tickets),
             tickets, f'2 códigos distintos {ctx.prefijo_ticket}XXXXXX')
    r.campos('Caja', cajero.get('/api/caja/actual').get_json(),
             {'ingresos': 100.0, 'egresos': 20.0, 'saldo_actual': 180.0})


@caso('CP-04-03', 73, 'HU04', 'Venta de 1 moto pagada con Yape',
      'Venta 2 total 15.0 pagada con 1 ticket; saldo de caja sigue en 180.0')
def cp_04_03(ctx, r):
    cajero = ctx.cliente('cajero')
    venta = ctx.api(cajero, '/api/ventas', {'items': [{'precio': 15, 'cantidad': 1}]}).get_json() or {}
    r.campos('Venta creada', venta, {'id_venta': 2, 'total': 15.0})
    resp = ctx.api(cajero, '/api/ventas/2/pago', {'metodo_pago': 'yape'})
    r.ver('Pago Yape (HTTP)', resp.status_code, 200)
    datos = resp.get_json() or {}
    r.ver('Venta 2', datos.get('estado'), 'pagada')
    tickets = datos.get('tickets', [])
    r.cumple('Tickets', len(tickets) == 1 and bool(re.fullmatch(
        re.escape(ctx.prefijo_ticket) + r'[0-9A-F]{6}', tickets[0])),
        tickets, f'1 código {ctx.prefijo_ticket}XXXXXX')
    r.ver('Saldo de caja', (cajero.get('/api/caja/actual').get_json() or {}).get('saldo_actual'), 180.0)


@caso('CP-04-04', 74, 'HU04', 'Pagar dos veces la venta 1',
      'HTTP 400 "Esta venta ya está pagada"; tickets en BD: 3')
def cp_04_04(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/ventas/1/pago', {'metodo_pago': 'efectivo'}),
           400, {'error': 'Esta venta ya está pagada'})
    r.ver('Tickets en BD', ctx.valor('SELECT count(*) FROM tickets'), 3)


@caso('CP-04-05', 75, 'HU04', 'Pago sin método',
      'Venta 3 creada (total 20.0); pago HTTP 400 "Indica el método de pago"; venta 3 pendiente')
def cp_04_05(ctx, r):
    cajero = ctx.cliente('cajero')
    venta = ctx.api(cajero, '/api/ventas', {'items': [{'precio': 20, 'cantidad': 1}]}).get_json() or {}
    r.campos('Venta creada', venta, {'id_venta': 3, 'total': 20.0})
    r.http(ctx.api(cajero, '/api/ventas/3/pago', {}), 400, {'error': 'Indica el método de pago'})
    r.ver('BD venta 3', ctx.valor('SELECT estado FROM ventas WHERE id_venta = 3'), 'pendiente')


@caso('CP-04-06', 76, 'HU04', 'Pagar una venta que no existe',
      'HTTP 404 {"error": "Venta no encontrada"}')
def cp_04_06(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/ventas/9999/pago', {'metodo_pago': 'efectivo'}),
           404, {'error': 'Venta no encontrada'})


@caso('CP-04-07', 77, 'HU04', 'Venta sin items',
      'HTTP 400 {"error": "La venta necesita al menos un item"}')
def cp_04_07(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/ventas', {'items': []}),
           400, {'error': 'La venta necesita al menos un item'})


ITEM_INVALIDO = {'error': 'Cada item necesita un precio y una cantidad mayores a 0'}


@caso('CP-04-08', 78, 'HU04', 'Venta con precio 0',
      'HTTP 400 "Cada item necesita un precio y una cantidad mayores a 0"')
def cp_04_08(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/ventas', {'items': [{'precio': 0, 'cantidad': 1}]}),
           400, ITEM_INVALIDO)


@caso('CP-04-09', 79, 'HU04', 'Venta con cantidad −1',
      'HTTP 400 "Cada item necesita un precio y una cantidad mayores a 0"')
def cp_04_09(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/ventas', {'items': [{'precio': 15, 'cantidad': -1}]}),
           400, ITEM_INVALIDO)


@caso('CP-04-10', 80, 'HU04', 'Venta con precio de texto',
      'HTTP 400 "Cada item necesita un precio y una cantidad mayores a 0"')
def cp_04_10(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/ventas', {'items': [{'precio': 'quince', 'cantidad': 1}]}),
           400, ITEM_INVALIDO)


# =====================================================================
# HU07 – Arqueo y cierre de caja (cierre)
# =====================================================================
@caso('CP-07-09', 81, 'HU07', 'Cerrar la caja 1',
      'HTTP 200: caja 1 cerrada, inicial 100.0, ingresos 100.0, egresos 20.0, final 180.0, fecha de cierre hoy')
def cp_07_09(ctx, r):
    resp = ctx.api(ctx.cliente('cajero'), '/api/caja/cerrar', {})
    r.ver('HTTP', resp.status_code, 200)
    datos = resp.get_json() or {}
    r.campos('Caja', datos, {
        'id_caja': 1, 'estado': 'cerrada', 'monto_inicial': 100.0, 'ingresos': 100.0,
        'egresos': 20.0, 'saldo_actual': 180.0, 'monto_final': 180.0})
    r.ver('Fecha de cierre', (datos.get('fecha_cierre') or '')[:10], ctx.fecha)


@caso('CP-07-10', 82, 'HU07', 'El cierre queda guardado en la BD',
      'cerrada | 100.00 | 180.00 | fechas de hoy, cierre posterior a la apertura')
def cp_07_10(ctx, r):
    fila = ctx.sql('SELECT estado, monto_inicial, monto_final, fecha_apertura, fecha_cierre '
                   'FROM cajas WHERE id_caja = 1')
    if not fila:
        r.falla('BD caja 1', 'no existe')
        return
    estado, inicial, final, apertura, cierre = fila[0]
    r.ver('BD (estado, inicial, final)', (estado, str(inicial), str(final)),
          ('cerrada', '100.00', '180.00'))
    r.cumple('Fechas', apertura.date() == ctx.hoy and cierre is not None and cierre >= apertura,
             f'{apertura:%Y-%m-%d %H:%M} → {cierre:%Y-%m-%d %H:%M}' if cierre else f'{apertura} → null',
             'apertura y cierre de hoy, cierre ≥ apertura')


@caso('CP-07-11', 83, 'HU07', 'Consultar caja después del cierre',
      'HTTP 404 {"error": "No hay una caja abierta"}')
def cp_07_11(ctx, r):
    r.http(ctx.cliente('cajero').get('/api/caja/actual'), 404, {'error': 'No hay una caja abierta'})


@caso('CP-07-12', 84, 'HU07', 'Cerrar dos veces',
      'HTTP 400 {"error": "No hay una caja abierta"}')
def cp_07_12(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/caja/cerrar', {}), 400, {'error': 'No hay una caja abierta'})


@caso('CP-07-13', 85, 'HU07', 'Registrar movimiento con la caja cerrada',
      'HTTP 400 {"error": "Primero debes abrir la caja"}')
def cp_07_13(ctx, r):
    r.http(ctx.api(ctx.cliente('cajero'), '/api/caja/movimientos',
                   {'tipo': 'ingreso', 'monto': 10, 'descripcion': 'Venta tardía'}),
           400, {'error': 'Primero debes abrir la caja'})


# =====================================================================
# HU06 – Gestión de mantenimiento de unidades de flota
# =====================================================================
@caso('CP-06-01', 86, 'HU06', 'Cargar repuestos de prueba',
      'INSERT 0 2; Batería 12V (3/1, no reponer) y Llanta infantil (0/2, reponer)')
def cp_06_01(ctx, r):
    insertados = ctx.sql(
        "INSERT INTO repuestos (nombre, stock, stock_minimo, estado) VALUES "
        "('Batería 12V', 3, 1, 'activo'), ('Llanta infantil', 0, 2, 'activo')")
    r.ver('INSERT', insertados, 2)
    r.http(ctx.cliente('admin').get('/api/repuestos'), 200, [
        {'id_repuesto': 1, 'nombre': 'Batería 12V', 'stock': 3, 'stock_minimo': 1,
         'necesita_reposicion': False},
        {'id_repuesto': 2, 'nombre': 'Llanta infantil', 'stock': 0, 'stock_minimo': 2,
         'necesita_reposicion': True},
    ])


@caso('CP-06-02', 87, 'HU06', 'Mantenimiento preventivo a Dino Rider #02',
      'HTTP 201: mantenimiento 1 en_proceso con Batería 12V; unidad 2 en mantenimiento; stock 3 → 2')
def cp_06_02(ctx, r):
    admin = ctx.cliente('admin')
    resp = ctx.api(admin, '/api/mantenimientos', {
        'id_flota': 2, 'tipo': 'preventivo',
        'observacion': 'Revisión de motor y cambio de batería', 'id_repuesto': 1})
    r.ver('HTTP', resp.status_code, 201)
    r.campos('Mantenimiento', resp.get_json(), {
        'id_mantenimiento': 1, 'id_flota': 2, 'flota': 'Dino Rider #02 (T-Rex Spiky)',
        'tipo': 'preventivo', 'estado': 'en_proceso', 'fecha_fin': None, 'repuesto': 'Batería 12V'})
    flota = admin.get('/api/flota?id_sucursal=1').get_json() or []
    r.ver('Unidad 2', next((f['estado'] for f in flota if f['id_flota'] == 2), None), 'mantenimiento')
    repuestos = admin.get('/api/repuestos').get_json() or []
    r.ver('Stock Batería 12V', next((x['stock'] for x in repuestos if x['id_repuesto'] == 1), None), 2)


@caso('CP-06-03', 88, 'HU06', 'Reservar una unidad en mantenimiento',
      'HTTP 400 "Dino Rider #02 (T-Rex Spiky) no está disponible en ese turno"')
def cp_06_03(ctx, r):
    r.http(ctx.api(ctx.cliente('ana'), '/api/reservas', {'items': [{'id_flota': 2, 'id_turno': 8}]}),
           400, {'error': 'Dino Rider #02 (T-Rex Spiky) no está disponible en ese turno'})


@caso('CP-06-04', 89, 'HU06', 'Mantenimiento a unidad inexistente',
      'HTTP 404 {"error": "La unidad de flota no existe"}')
def cp_06_04(ctx, r):
    r.http(ctx.api(ctx.cliente('admin'), '/api/mantenimientos', {'id_flota': 99, 'tipo': 'correctivo'}),
           404, {'error': 'La unidad de flota no existe'})


@caso('CP-06-05', 90, 'HU06', 'Mantenimiento sin tipo',
      'HTTP 400 "Indica el tipo de mantenimiento"; unidad 3 sigue disponible')
def cp_06_05(ctx, r):
    r.http(ctx.api(ctx.cliente('admin'), '/api/mantenimientos',
                   {'id_flota': 3, 'observacion': 'Ruido en las ruedas'}),
           400, {'error': 'Indica el tipo de mantenimiento'})
    r.ver('BD unidad 3', _estado_flota(ctx, 3), 'disponible')


@caso('CP-06-06', 91, 'HU06', 'Usar repuesto sin stock',
      'HTTP 400 "No hay stock de Llanta infantil"; unidad 3 sigue disponible')
def cp_06_06(ctx, r):
    r.http(ctx.api(ctx.cliente('admin'), '/api/mantenimientos',
                   {'id_flota': 3, 'tipo': 'correctivo', 'observacion': 'Llanta pinchada', 'id_repuesto': 2}),
           400, {'error': 'No hay stock de Llanta infantil'})
    r.ver('BD unidad 3', _estado_flota(ctx, 3), 'disponible')


@caso('CP-06-07', 92, 'HU06', 'Repuesto inexistente',
      'HTTP 404 {"error": "El repuesto no existe"}')
def cp_06_07(ctx, r):
    r.http(ctx.api(ctx.cliente('admin'), '/api/mantenimientos',
                   {'id_flota': 3, 'tipo': 'correctivo', 'id_repuesto': 99}),
           404, {'error': 'El repuesto no existe'})


@caso('CP-06-08', 93, 'HU06', 'Repuestos que necesitan reposición',
      'Solo 1 resultado: Llanta infantil (stock 0, mínimo 2)')
def cp_06_08(ctx, r):
    r.http(ctx.cliente('admin').get('/api/repuestos?bajo_stock=1'), 200, [
        {'id_repuesto': 2, 'nombre': 'Llanta infantil', 'stock': 0, 'stock_minimo': 2,
         'necesita_reposicion': True}])


@caso('CP-06-09', 94, 'HU06', 'Finalizar el mantenimiento 1',
      'HTTP 200: mantenimiento 1 finalizado con fecha de hoy; unidad 2 disponible')
def cp_06_09(ctx, r):
    admin = ctx.cliente('admin')
    resp = ctx.api(admin, '/api/mantenimientos/1/finalizar', {})
    r.ver('HTTP', resp.status_code, 200)
    datos = resp.get_json() or {}
    r.campos('Mantenimiento', datos, {'id_mantenimiento': 1, 'estado': 'finalizado'})
    r.ver('Fecha de fin', (datos.get('fecha_fin') or '')[:10], ctx.fecha)
    flota = admin.get('/api/flota?id_sucursal=1').get_json() or []
    r.ver('Unidad 2', next((f['estado'] for f in flota if f['id_flota'] == 2), None), 'disponible')


@caso('CP-06-10', 95, 'HU06', 'Finalizar dos veces',
      'HTTP 400 {"error": "Este mantenimiento ya fue finalizado"}')
def cp_06_10(ctx, r):
    r.http(ctx.api(ctx.cliente('admin'), '/api/mantenimientos/1/finalizar', {}),
           400, {'error': 'Este mantenimiento ya fue finalizado'})


@caso('CP-06-11', 96, 'HU06', 'Finalizar mantenimiento inexistente',
      'HTTP 404 {"error": "Mantenimiento no encontrado"}')
def cp_06_11(ctx, r):
    r.http(ctx.api(ctx.cliente('admin'), '/api/mantenimientos/50/finalizar', {}),
           404, {'error': 'Mantenimiento no encontrado'})


@caso('CP-06-12', 97, 'HU06', 'Historial de Dino Rider #02',
      '1 registro: preventivo, finalizado, "Revisión de motor y cambio de batería", Batería 12V, fechas de hoy')
def cp_06_12(ctx, r):
    resp = ctx.cliente('admin').get('/api/flota/2/mantenimientos')
    r.ver('HTTP', resp.status_code, 200)
    historial = resp.get_json() or []
    r.ver('Registros', len(historial), 1)
    if historial:
        m = historial[0]
        r.campos('Registro', m, {
            'id_mantenimiento': 1, 'tipo': 'preventivo', 'estado': 'finalizado',
            'observacion': 'Revisión de motor y cambio de batería', 'repuesto': 'Batería 12V'})
        r.ver('Fechas (inicio, fin)', [(m['fecha_inicio'] or '')[:10], (m['fecha_fin'] or '')[:10]],
              [ctx.fecha, ctx.fecha])


@caso('CP-06-13', 98, 'HU06', 'Historial de unidad inexistente',
      'HTTP 404 {"error": "La unidad de flota no existe"}')
def cp_06_13(ctx, r):
    r.http(ctx.cliente('admin').get('/api/flota/99/mantenimientos'),
           404, {'error': 'La unidad de flota no existe'})


# =====================================================================
# HU08 – El menú de caja depende de la sede del cajero
# (flota por turno en Real Plaza/Mega Plaza, entrada por tiempo en Hoyos
# Rubio). Van al final a propósito: reasignan la sede del cajero de
# pruebas, y ningún caso anterior depende de ese valor.
# =====================================================================

@caso('CP-08-01', 99, 'HU08', 'Cajero asignado a Real Plaza ve flota, no entradas',
      '/caja/flota muestra "Vender / Alquilar Flota" y no "Vender Entradas"; hay flota alquilable')
def cp_08_01(ctx, r):
    ctx.sql("UPDATE usuarios SET id_sucursal = 1 WHERE correo = :c", c=CAJERO[0])

    cliente = ctx.nuevo_cliente()
    ctx.login(cliente, *CAJERO)

    pagina = cliente.get('/caja/flota')
    r.ver('HTTP /caja/flota', pagina.status_code, 200)
    r.ver('Muestra "Vender / Alquilar Flota"', b'Vender / Alquilar Flota' in pagina.data, True)
    r.ver('No muestra "Vender Entradas"', b'Vender Entradas' in pagina.data, False)

    alquilable = cliente.get('/api/flota/alquilable?id_sucursal=1').get_json() or []
    r.ver('Hay flota alquilable en Real Plaza', len(alquilable) > 0, True)


@caso('CP-08-02', 100, 'HU08', 'Cajero asignado a Hoyos Rubio ve entradas, no flota',
      '/caja/entradas muestra "Vender Entradas" y no "Vender / Alquilar Flota"; hay zonas activas')
def cp_08_02(ctx, r):
    id_hoyos_rubio = ctx.valor(
        "SELECT id_sucursal FROM sucursales WHERE nombre = 'Hoyos Rubio'")
    ctx.sql("UPDATE usuarios SET id_sucursal = :s WHERE correo = :c",
            s=id_hoyos_rubio, c=CAJERO[0])

    cliente = ctx.nuevo_cliente()
    ctx.login(cliente, *CAJERO)

    pagina = cliente.get('/caja/entradas')
    r.ver('HTTP /caja/entradas', pagina.status_code, 200)
    r.ver('Muestra "Vender Entradas"', b'Vender Entradas' in pagina.data, True)
    r.ver('No muestra "Vender / Alquilar Flota"', b'Vender / Alquilar Flota' in pagina.data, False)

    zonas = cliente.get(f'/api/sedes/{id_hoyos_rubio}/zonas').get_json() or []
    r.ver('Hay zonas activas en Hoyos Rubio', len(zonas) > 0, True)


# =====================================================================
# HU09 – Reasignar la sede de un cajero (con caja abierta de por medio) y
# lecturas manuales obligatorias al abrir/cerrar caja en sedes con flota.
# También van al final: dependen del cajero de pruebas y de que ninguna
# caja quede abierta para los casos anteriores.
# =====================================================================

def _id_sucursal_por_nombre(ctx, nombre):
    return ctx.valor("SELECT id_sucursal FROM sucursales WHERE nombre = :n", n=nombre)


def _id_cajero_pruebas(ctx):
    return ctx.valor("SELECT id_usuario FROM usuarios WHERE correo = :c", c=CAJERO[0])


def _unidades_flota_de(ctx, id_sucursal):
    filas = ctx.sql("SELECT id_flota FROM flota WHERE id_sucursal = :s", s=id_sucursal)
    return [f[0] for f in filas]


def _cajero_logueado(ctx):
    """Cliente nuevo + login: la sede se lee de la BD recién al iniciar sesión,
    así que hace falta un login fresco cada vez que cambia."""
    cliente = ctx.nuevo_cliente()
    ctx.login(cliente, *CAJERO)
    return cliente


@caso('CP-09-01', 101, 'HU09', 'Admin reasigna la sede de un cajero sin caja abierta',
      'HTTP 200; el cajero queda asignado a Real Plaza en la BD')
def cp_09_01(ctx, r):
    id_real_plaza = _id_sucursal_por_nombre(ctx, 'Real Plaza')
    id_cajero = _id_cajero_pruebas(ctx)

    resp = ctx.cliente('admin').put(f'/api/admin/usuarios/{id_cajero}', json={'id_sucursal': id_real_plaza})
    r.ver('HTTP', resp.status_code, 200)
    r.ver('BD id_sucursal', ctx.valor(
        "SELECT id_sucursal FROM usuarios WHERE id_usuario = :u", u=id_cajero), id_real_plaza)


@caso('CP-09-02', 102, 'HU09', 'Abrir caja en sede con flota sin registrar todas las lecturas',
      'HTTP 400 "No se puede abrir la caja: Falta registrar la lectura de..."')
def cp_09_02(ctx, r):
    cliente = _cajero_logueado(ctx)
    id_real_plaza = _id_sucursal_por_nombre(ctx, 'Real Plaza')

    resp = ctx.api(cliente, '/api/caja/abrir', {'monto_inicial': 50, 'id_sucursal': id_real_plaza, 'lecturas': []})
    r.ver('HTTP', resp.status_code, 400)
    r.mensaje(resp, 'No se puede abrir la caja: Falta registrar la lectura de')
    r.ver('Caja abierta en BD', ctx.valor("SELECT count(*) FROM cajas WHERE estado = 'abierta'"), 0)


@caso('CP-09-03', 103, 'HU09', 'Abrir caja en sede con flota con todas las lecturas completas',
      'HTTP 201; se crea una lectura de apertura por cada unidad de Real Plaza')
def cp_09_03(ctx, r):
    cliente = _cajero_logueado(ctx)
    id_real_plaza = _id_sucursal_por_nombre(ctx, 'Real Plaza')
    unidades = _unidades_flota_de(ctx, id_real_plaza)
    lecturas = [{'id_flota': f, 'lectura_manual': 0} for f in unidades]

    resp = ctx.api(cliente, '/api/caja/abrir', {'monto_inicial': 50, 'id_sucursal': id_real_plaza, 'lecturas': lecturas})
    r.ver('HTTP', resp.status_code, 201)
    datos = resp.get_json() or {}
    r.ver('id_sucursal de la caja', datos.get('id_sucursal'), id_real_plaza)
    r.ver('Lecturas de apertura en BD', ctx.valor(
        "SELECT count(*) FROM lecturas_flota WHERE id_caja = :c AND momento = 'apertura'",
        c=datos.get('id_caja')), len(unidades))


@caso('CP-09-04', 104, 'HU09', 'No se puede reasignar la sede de un cajero con la caja abierta',
      'HTTP 409 "...tiene la caja abierta en Real Plaza..."; la sede en BD no cambia')
def cp_09_04(ctx, r):
    id_cajero = _id_cajero_pruebas(ctx)
    id_mega_plaza = _id_sucursal_por_nombre(ctx, 'Mega Plaza')
    id_real_plaza = _id_sucursal_por_nombre(ctx, 'Real Plaza')

    resp = ctx.cliente('admin').put(f'/api/admin/usuarios/{id_cajero}', json={'id_sucursal': id_mega_plaza})
    r.ver('HTTP', resp.status_code, 409)
    r.mensaje(resp, 'tiene la caja abierta en Real Plaza')
    r.ver('BD id_sucursal sin cambios', ctx.valor(
        "SELECT id_sucursal FROM usuarios WHERE id_usuario = :u", u=id_cajero), id_real_plaza)


@caso('CP-09-05', 105, 'HU09', 'Cerrar caja en sede con flota sin lecturas de cierre',
      'HTTP 400 "No se puede cerrar la caja: Falta registrar la lectura de..."; caja sigue abierta')
def cp_09_05(ctx, r):
    cliente = _cajero_logueado(ctx)
    resp = ctx.api(cliente, '/api/caja/cerrar', {'lecturas': []})
    r.ver('HTTP', resp.status_code, 400)
    r.mensaje(resp, 'No se puede cerrar la caja: Falta registrar la lectura de')
    r.ver('Caja sigue abierta en BD', ctx.valor("SELECT count(*) FROM cajas WHERE estado = 'abierta'"), 1)


@caso('CP-09-06', 106, 'HU09', 'Cerrar caja con lecturas completas; ahora sí procede el cambio de sede',
      'HTTP 200 al cerrar; luego HTTP 200 al reasignar la sede a Mega Plaza')
def cp_09_06(ctx, r):
    cliente = _cajero_logueado(ctx)
    id_real_plaza = _id_sucursal_por_nombre(ctx, 'Real Plaza')
    unidades = _unidades_flota_de(ctx, id_real_plaza)
    lecturas = [{'id_flota': f, 'lectura_manual': 0} for f in unidades]

    resp = ctx.api(cliente, '/api/caja/cerrar', {'lecturas': lecturas})
    r.ver('HTTP cerrar', resp.status_code, 200)
    r.ver('Lecturas de cierre en BD', ctx.valor(
        "SELECT count(*) FROM lecturas_flota WHERE momento = 'cierre'"), len(unidades))

    id_cajero = _id_cajero_pruebas(ctx)
    id_mega_plaza = _id_sucursal_por_nombre(ctx, 'Mega Plaza')
    resp2 = ctx.cliente('admin').put(f'/api/admin/usuarios/{id_cajero}', json={'id_sucursal': id_mega_plaza})
    r.ver('HTTP reasignar sede', resp2.status_code, 200)
    r.ver('BD id_sucursal actualizada', ctx.valor(
        "SELECT id_sucursal FROM usuarios WHERE id_usuario = :u", u=id_cajero), id_mega_plaza)


@caso('CP-09-07', 107, 'HU09', 'En Hoyos Rubio, abrir y cerrar caja no exige lecturas',
      'HTTP 201 al abrir sin lecturas y HTTP 200 al cerrar sin lecturas')
def cp_09_07(ctx, r):
    id_cajero = _id_cajero_pruebas(ctx)
    id_hoyos_rubio = _id_sucursal_por_nombre(ctx, 'Hoyos Rubio')
    ctx.sql("UPDATE usuarios SET id_sucursal = :s WHERE id_usuario = :u", s=id_hoyos_rubio, u=id_cajero)

    cliente = _cajero_logueado(ctx)
    resp = ctx.api(cliente, '/api/caja/abrir', {'monto_inicial': 30, 'id_sucursal': id_hoyos_rubio, 'lecturas': []})
    r.ver('HTTP abrir', resp.status_code, 201)

    resp2 = ctx.api(cliente, '/api/caja/cerrar', {'lecturas': []})
    r.ver('HTTP cerrar', resp2.status_code, 200)
