from datetime import date, datetime, time, timedelta

from app.database import db
from app.models.Rol import Rol
from app.models.Sucursal import Sucursal
from app.models.Flota import Dinosaurio, Carro, Moto


def cargar_datos_iniciales():
    """Crea los roles, las sedes, la flota y los turnos del día.

    Se puede ejecutar varias veces:
    solo agrega los datos que todavía no existen.
    """

    _cargar_roles()
    _cargar_sedes()

    # Necesitamos los id_sucursal ya asignados antes de crear flota,
    # así que confirmamos lo anterior primero.
    db.session.commit()

    _cargar_flota()

    # Igual aquí: necesitamos los id_flota antes de crear los turnos.
    db.session.commit()

    _cargar_turnos()

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