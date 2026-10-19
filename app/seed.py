import os
from datetime import date, datetime, time, timedelta

from werkzeug.security import generate_password_hash

from app.database import db
from app.models.Rol import Rol
from app.models.usuario import Usuario
from app.models.Sucursal import Sucursal
from app.models.Flota import Dinosaurio, Carro, Moto
from app.models.Zona import Zona
from app.models.PaqueteTarifa import PaqueteTarifa


def cargar_datos_iniciales():
    """Crea los roles, las sedes, la flota y los turnos del día.

    Se puede ejecutar varias veces:
    solo agrega los datos que todavía no existen.
    """

    _cargar_roles()
    db.session.flush()
    _cargar_cajero()
    _cargar_sedes()

    # Necesitamos los id_sucursal ya asignados antes de crear flota,
    # así que confirmamos lo anterior primero.
    db.session.commit()

    _cargar_flota()

    # Igual aquí: necesitamos los id_flota antes de crear los turnos.
    db.session.commit()

    _cargar_turnos()

    db.session.commit()

    # Va después de todo lo anterior a propósito: así nunca corre antes de
    # que Real Plaza/Mega Plaza ya tengan sus id_sucursal 1/2 asignados
    # (los 98 casos de app/pruebas/casos.py dependen de esos IDs).
    _cargar_sede_hoyos_rubio()

    db.session.commit()


def _cargar_roles():

    roles = {
        'administrador': 'Acceso total al sistema',
        'cajero': 'Ventas y caja',
        'cliente': 'Cliente del parque',
    }

    for nombre, descripcion in roles.items():
        if not Rol.query.filter_by(nombre=nombre).first():
            db.session.add(
                Rol(
                    nombre=nombre,
                    descripcion=descripcion
                )
            )


def _cargar_cajero():
    """Crea la cuenta única del cajero a partir del .env
    (CAJERO_CORREO y CAJERO_CONTRASENA).

    El registro público siempre crea clientes, así que esta es la única
    vía para tener un cajero. Si ya existe un usuario con ese rol no se
    crea otro, y si faltan las variables no se crea nada.
    """

    correo = os.getenv('CAJERO_CORREO', '').strip().lower()
    contrasena = os.getenv('CAJERO_CONTRASENA', '')

    if not correo or not contrasena:
        print('[seed] Sin CAJERO_CORREO/CAJERO_CONTRASENA en .env: '
              'no se crea la cuenta de cajero.')
        return

    rol = Rol.query.filter_by(nombre='cajero').first()

    if rol is None or Usuario.query.filter_by(id_rol=rol.id_rol).first():
        return

    if Usuario.query.filter_by(correo=correo).first():
        print(f'[seed] El correo {correo} ya está registrado con otro rol: '
              'usa otro en CAJERO_CORREO.')
        return

    db.session.add(
        Usuario(
            nombre='Cajero',
            apellido='Dino Park',
            correo=correo,
            contrasena=generate_password_hash(contrasena),
            estado=True,
            id_rol=rol.id_rol,
        )
    )


def _cargar_sedes():

    sedes = {
        'Real Plaza': 'Real Plaza Cajamarca (Nivel 2, Explanada Jurásica)',
        'Mega Plaza': 'Mega Plaza Cajamarca (Primer Nivel, Zona Recreativa Central)',
    }

    for nombre, direccion in sedes.items():
        if not Sucursal.query.filter_by(nombre=nombre).first():
            db.session.add(
                Sucursal(
                    nombre=nombre,
                    direccion=direccion
                )
            )


def _cargar_flota():
    """Flota de ejemplo, con los precios que ya anuncia el landing
    (Dinosaurios y Motos S/15.00, Carros S/20.00)."""

    # Si ya hay al menos una unidad de flota, no volvemos a sembrar
    # (evita duplicar unidades cada vez que se reinicia el servidor).
    if Dinosaurio.query.first() or Carro.query.first() or Moto.query.first():
        return

    real_plaza = Sucursal.query.filter_by(nombre='Real Plaza').first()
    mega_plaza = Sucursal.query.filter_by(nombre='Mega Plaza').first()

    if real_plaza is None or mega_plaza is None:
        # No deberían faltar, pero si faltan no seguimos para no
        # crear flota sin sede válida.
        return

    unidades = [
        # --- Real Plaza ---
        Dinosaurio(
            nombre='Dino Rider #01 (T-Rex Rexy)',
            modelo='Dinosaurio mecánico con sonido',
            especie='T-Rex',
            precio_hora=15.00,
            id_sucursal=real_plaza.id_sucursal,
        ),
        Dinosaurio(
            nombre='Dino Rider #02 (T-Rex Spiky)',
            modelo='Velocidad segura monitoreada',
            especie='T-Rex',
            precio_hora=15.00,
            id_sucursal=real_plaza.id_sucursal,
        ),
        Carro(
            nombre='Super Carro Rojo AMG #04',
            modelo='2 asientos con cinturón y control parental',
            velocidad='Media',
            precio_hora=20.00,
            id_sucursal=real_plaza.id_sucursal,
        ),
        Moto(
            nombre='Moto GP Dino Ninja #07',
            modelo='Ruedas de entrenamiento estabilizadas',
            cilindrada='Infantil',
            precio_hora=15.00,
            id_sucursal=real_plaza.id_sucursal,
        ),
        Moto(
            nombre='Moto GP Dino Ninja #08',
            modelo='Luces LED y sonido de aceleración',
            cilindrada='Infantil',
            precio_hora=15.00,
            id_sucursal=real_plaza.id_sucursal,
        ),

        # --- Mega Plaza ---
        Dinosaurio(
            nombre='Dino Rider #05 (Triceratops Trike)',
            modelo='Circuito extendido',
            especie='Triceratops',
            precio_hora=15.00,
            id_sucursal=mega_plaza.id_sucursal,
        ),
        Carro(
            nombre='Safari Buggy Jurásico #06',
            modelo='Minicar eléctrico estilo todoterreno',
            velocidad='Media',
            precio_hora=20.00,
            id_sucursal=mega_plaza.id_sucursal,
        ),
        Moto(
            nombre='Moto GP Dino Ninja #09',
            modelo='Carcasa de triceratops con LED',
            cilindrada='Infantil',
            precio_hora=15.00,
            id_sucursal=mega_plaza.id_sucursal,
        ),
    ]

    db.session.add_all(unidades)


def _cargar_turnos():
    """Turnos de hoy para cada unidad de flota que todavía no tenga
    turnos programados (franjas de 20 minutos, de 10:00 a 13:00)."""

    hoy = date.today()

    horarios = [
        (time(10, 0), time(10, 20)),
        (time(10, 30), time(10, 50)),
        (time(11, 0), time(11, 20)),
        (time(11, 30), time(11, 50)),
        (time(12, 0), time(12, 20)),
        (time(12, 30), time(12, 50)),
    ]

    todas_las_unidades = (
        Dinosaurio.query.all()
        + Carro.query.all()
        + Moto.query.all()
    )

    for unidad in todas_las_unidades:

        # Si esta unidad ya tiene turnos (de una siembra anterior),
        # no le agregamos más.
        if unidad.turnos:
            continue

        for hora_inicio, hora_fin in horarios:
            from app.models.Turno import Turno

            db.session.add(
                Turno(
                    fecha=datetime.combine(hoy, time()),
                    horario_inicio=datetime.combine(hoy, hora_inicio),
                    horario_fin=datetime.combine(hoy, hora_fin),
                    estado='disponible',
                    capacidad=1,
                    id_flota=unidad.id_flota,
                )
            )


def _cargar_sede_hoyos_rubio():
    """Sede Hoyos Rubio: no alquila flota, vende entrada por tiempo a dos
    zonas (inflable y arenero). Se puede ejecutar varias veces: si la sede
    ya existe, no vuelve a crear nada."""

    if Sucursal.query.filter_by(nombre='Hoyos Rubio').first():
        return

    sede = Sucursal(
        nombre='Hoyos Rubio',
        direccion='Jr. Hoyos Rubio (Cajamarca)',
        estado='activa',
        # Monto de ejemplo: el administrador lo ajusta desde /admin/sedes.
        monto_adicional_exceso=10.00,
    )
    db.session.add(sede)
    db.session.flush()

    aventura = Zona(
        id_sucursal=sede.id_sucursal,
        nombre='Aventura Jurásica',
        descripcion='Zona inflable',
    )
    arenero = Zona(
        id_sucursal=sede.id_sucursal,
        nombre='Arenero Dino',
        descripcion='Zona de arenero',
    )
    db.session.add_all([aventura, arenero])
    db.session.flush()

    db.session.add_all([
        # --- Aventura Jurásica ---
        PaqueteTarifa(
            id_zona=aventura.id_zona,
            nombre='Expedición Individual - Ruta larga',
            tipo='individual', duracion_minutos=40, precio=30.00,
            es_por_ninio=True, minimo_cantidad=1, orden=1,
        ),
        PaqueteTarifa(
            id_zona=aventura.id_zona,
            nombre='Expedición Individual - Ruta corta',
            tipo='individual', duracion_minutos=20, precio=20.00,
            es_por_ninio=True, minimo_cantidad=1, orden=2,
        ),
        PaqueteTarifa(
            id_zona=aventura.id_zona,
            nombre='Pack Friends / Hermanos - 40 min',
            tipo='pack_friends', duracion_minutos=40, precio=28.50,
            es_por_ninio=True, minimo_cantidad=2, orden=3,
        ),
        PaqueteTarifa(
            id_zona=aventura.id_zona,
            nombre='Pack Friends / Hermanos - 20 min',
            tipo='pack_friends', duracion_minutos=20, precio=18.50,
            es_por_ninio=True, minimo_cantidad=2, orden=4,
        ),
        PaqueteTarifa(
            id_zona=aventura.id_zona,
            nombre='Pack Escolar - 40 min',
            tipo='pack_escolar', duracion_minutos=40, precio=25.00,
            es_por_ninio=True, minimo_cantidad=15, orden=5,
        ),
        PaqueteTarifa(
            id_zona=aventura.id_zona,
            nombre='Pack Guía / Acompañante Adulto',
            tipo='pack_guia', duracion_minutos=None, precio=10.00,
            es_por_ninio=True, minimo_cantidad=1, orden=6,
        ),

        # --- Arenero Dino ---
        PaqueteTarifa(
            id_zona=arenero.id_zona,
            nombre='Entrada Arenero - 20 min',
            tipo='general', duracion_minutos=20, precio=15.00,
            es_por_ninio=True, minimo_cantidad=1, orden=1,
        ),
        PaqueteTarifa(
            id_zona=arenero.id_zona,
            nombre='Entrada Arenero - 30 min',
            tipo='general', duracion_minutos=30, precio=20.00,
            es_por_ninio=True, minimo_cantidad=1, orden=2,
        ),
        PaqueteTarifa(
            id_zona=arenero.id_zona,
            nombre='Pack Friends - 20 min',
            tipo='pack_friends', duracion_minutos=20, precio=12.50,
            es_por_ninio=True, minimo_cantidad=2, orden=3,
        ),
        PaqueteTarifa(
            id_zona=arenero.id_zona,
            nombre='Pack Friends - 30 min',
            tipo='pack_friends', duracion_minutos=30, precio=17.50,
            es_por_ninio=True, minimo_cantidad=2, orden=4,
        ),
    ])