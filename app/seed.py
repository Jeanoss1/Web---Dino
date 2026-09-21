"""Datos de prueba de Dino Park.  Uso:

    flask --app run seed            # datos base
    flask --app run seed --demo     # + ventas de las últimas semanas

Se puede ejecutar varias veces: solo agrega lo que todavía no existe.
"""
import os
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from werkzeug.security import generate_password_hash

from app.database import db
from app.models.Caja import Caja
from app.models.Cajero import Cajero
from app.models.Cliente import Cliente
from app.models.DetalleVenta import DetalleVenta
from app.models.Flota import Carro, Dinosaurio, Flota, Moto
from app.models.LecturaCaja import LecturaCaja
from app.models.MovimientoCaja import MovimientoCaja
from app.models.RegistroUso import RegistroUso
from app.models.Repuesto import Repuesto
from app.models.Rol import Rol
from app.models.Sucursal import Sucursal
from app.models.Tarifa import Tarifa
from app.models.Turno import AsignacionTurno, Turno
from app.models.usuario import Usuario
from app.models.Venta import Venta
from app.services import lecturas as servicio_lecturas
from app.services import turnos as servicio_turnos

CLAVE_POR_DEFECTO = 'Dino2026!'
ADMIN_CORREO = 'admin@dinopark.pe'

SEDES = [
    ('Real Plaza', 'Real Plaza Cajamarca (Nivel 2, Explanada Jurásica)', 'activa', 'realplaza'),
    ('Mega Plaza', 'Mega Plaza Cajamarca (Primer Nivel, Zona Recreativa Central)', 'activa', 'megaplaza'),
    ('Hoyos Rubio', 'Hoyos Rubio, Cajamarca (próximamente)', 'inactiva', None),
]

TURNOS = [
    ('Completo mañana', 'completo', time(10, 0), time(18, 0)),
    ('Completo tarde', 'completo', time(14, 0), time(22, 0)),
    ('Medio mañana', 'medio', time(10, 0), time(14, 0)),
    ('Medio tarde', 'medio', time(18, 0), time(22, 0)),
]


def cargar_datos_iniciales(demo=False):
    clave = os.getenv('SEED_PASSWORD') or CLAVE_POR_DEFECTO
    _roles()
    _tarifa()
    _turnos()
    _sedes()
    db.session.commit()
    _admin(clave)
    _cajeros(clave)
    _clientes(clave)
    _flota()
    _repuestos()
    db.session.commit()
    _horarios()
    db.session.commit()
    if demo:
        _ventas_demo()
        db.session.commit()
    _mostrar_credenciales(clave)


def _roles():
    for nombre, desc in {'administrador': 'Acceso total al sistema', 'cajero': 'Ventas y caja de su sede',
                         'cliente': 'Cliente del parque'}.items():
        if not Rol.query.filter_by(nombre=nombre).first():
            db.session.add(Rol(nombre=nombre, descripcion=desc))
    db.session.flush()


def _tarifa():
    if not Tarifa.query.first():
        db.session.add(Tarifa(nombre='Estándar', precio=Decimal('10.00'), minutos=12, activa=True))


def _turnos():
    for nombre, tipo, ini, fin in TURNOS:
        if not Turno.query.filter_by(nombre=nombre).first():
            db.session.add(Turno(nombre=nombre, tipo=tipo, hora_inicio=ini, hora_fin=fin))


def _sedes():
    for nombre, direccion, estado, _ in SEDES:
        if not Sucursal.query.filter_by(nombre=nombre).first():
            db.session.add(Sucursal(nombre=nombre, direccion=direccion, estado=estado))


def _usuario(rol, nombre, apellido, correo, clave):
    u = Usuario.query.filter_by(correo=correo).first()
    if u is None:
        u = Usuario(nombre=nombre, apellido=apellido, correo=correo, estado=True,
                    contrasena=generate_password_hash(clave),
                    id_rol=Rol.query.filter_by(nombre=rol).first().id_rol)
        db.session.add(u)
        db.session.flush()
    return u


def _admin(clave):
    _usuario('administrador', 'Administrador', 'Dino Park', ADMIN_CORREO, clave)


def _cajeros(clave):
    for nombre_sede, _, _, slug in SEDES:
        if slug is None:
            continue
        sede = Sucursal.query.filter_by(nombre=nombre_sede).first()
        for n, tipo in ((1, 'completo'), (2, 'medio')):
            u = _usuario('cajero', f'Cajero {n}', nombre_sede, f'cajero{n}.{slug}@dinopark.pe', clave)
            if u.cajero is None:
                db.session.add(Cajero(id_usuario=u.id_usuario, id_sucursal=sede.id_sucursal,
                                      tipo_turno=tipo, estado='activo'))
    db.session.flush()


def _clientes(clave):
    for i in range(1, 4):
        u = _usuario('cliente', f'Cliente {i}', 'Ejemplo', f'cliente{i}@ejemplo.pe', clave)
        if u.cliente is None:
            db.session.add(Cliente(id_usuario=u.id_usuario, nombre=f'Cliente {i}', apellido='Ejemplo',
                                   dni=f'7000000{i}', telefono=f'90000000{i}', correo=u.correo))
    db.session.flush()


def _flota():
    if Flota.query.first():
        return
    real = Sucursal.query.filter_by(nombre='Real Plaza').first().id_sucursal
    mega = Sucursal.query.filter_by(nombre='Mega Plaza').first().id_sucursal
    db.session.add_all([
        Dinosaurio(nombre='Dino Rider #01 (T-Rex Rexy)', modelo='Dinosaurio mecánico con sonido',
                   especie='T-Rex', id_sucursal=real),
        Dinosaurio(nombre='Dino Rider #02 (T-Rex Spiky)', modelo='Velocidad segura monitoreada',
                   especie='T-Rex', id_sucursal=real),
        Carro(nombre='Super Carro Rojo AMG #04', modelo='2 asientos con cinturón y control parental',
              velocidad='Media', id_sucursal=real),
        Moto(nombre='Moto GP Dino Ninja #07', modelo='Ruedas de entrenamiento estabilizadas',
             cilindrada='Infantil', id_sucursal=real),
        Moto(nombre='Moto GP Dino Ninja #08', modelo='Luces LED y sonido de aceleración',
             cilindrada='Infantil', id_sucursal=real),
        Dinosaurio(nombre='Dino Rider #05 (Triceratops Trike)', modelo='Circuito extendido',
                   especie='Triceratops', id_sucursal=mega),
        Carro(nombre='Safari Buggy Jurásico #06', modelo='Minicar eléctrico estilo todoterreno',
              velocidad='Media', id_sucursal=mega),
        Moto(nombre='Moto GP Dino Ninja #09', modelo='Carcasa de triceratops con LED',
             cilindrada='Infantil', id_sucursal=mega),
    ])
    db.session.flush()
    # Lecturas de ejemplo del contador fisico que ya traen las atracciones:
    # dinosaurios entre 400 y 700 minutos; carros y motos, pocos encendidos.
    azar = random.Random(7)
    for f in Flota.query.order_by(Flota.id_flota):
        f.lectura_manual = azar.randint(400, 700) if f.tipo_contador == 'minutos' else azar.randint(1, 5)


def _repuestos():
    if not Repuesto.query.first():
        db.session.add_all([
            Repuesto(nombre='Batería 12V', stock=6, stock_minimo=2),
            Repuesto(nombre='Llanta de repuesto', stock=8, stock_minimo=3),
            Repuesto(nombre='Motor de tracción', stock=1, stock_minimo=2),
        ])


def _turno_para(cajero, indice_semana):
    """Los cajeros rotan entre mañana y tarde semana a semana."""
    opciones = [t for t in Turno.query.filter_by(tipo=cajero.tipo_turno).order_by(Turno.hora_inicio)]
    return opciones[(indice_semana + cajero.id_cajero) % len(opciones)]


def _horarios(semanas_atras=6, semanas_adelante=1):
    """Horario rotativo: 6 días por semana, un día libre que va cambiando."""
    lunes_actual = servicio_turnos.lunes_de(date.today())
    for k in range(-semanas_atras, semanas_adelante + 1):
        lunes = lunes_actual + timedelta(weeks=k)
        if AsignacionTurno.query.filter(AsignacionTurno.fecha == lunes).first():
            continue
        for cajero in Cajero.query.all():
            libre = (cajero.id_cajero * 2 + k) % 7
            turno = _turno_para(cajero, k)
            for i in range(7):
                if i != libre:
                    db.session.add(AsignacionTurno(id_cajero=cajero.id_cajero, id_turno=turno.id_turno,
                                                   fecha=lunes + timedelta(days=i)))


def _ventas_demo(dias=35):
    """Historial de ventas presenciales con sus cierres de caja (datos inventados)."""
    if Venta.query.first():
        print('[seed] Ya hay ventas; no se agrega el historial de demostración.')
        return
    azar = random.Random(42)
    precio, minutos_bloque = Decimal('10.00'), 12
    hoy = date.today()
    for atras in range(dias, 0, -1):
        dia = hoy - timedelta(days=atras)
        for asignacion in AsignacionTurno.query.filter_by(fecha=dia).all():
            cajero = asignacion.cajero
            unidades = Flota.query.filter_by(id_sucursal=cajero.id_sucursal).all()
            turno = asignacion.turno
            inicio_turno = datetime.combine(dia, turno.hora_inicio)
            caja = Caja(id_usuario=cajero.id_usuario, id_sucursal=cajero.id_sucursal,
                        fecha_apertura=inicio_turno - timedelta(minutes=5),
                        fecha_cierre=datetime.combine(dia, turno.hora_fin) + timedelta(minutes=5),
                        monto_inicial=Decimal('50.00'), estado='cerrada')
            db.session.add(caja)
            db.session.flush()
            efectivo = yape = 0
            vendidos = usados = 0
            por_unidad = {}          # id_flota -> {'uso': fisico, 'sistema': contador del sistema, 'vendido': ...}
            n_ventas = azar.randint(3, 6) * (2 if turno.tipo == 'completo' else 1)
            for _ in range(n_ventas):
                bloques = azar.choice([1, 1, 1, 2, 2, 3])
                unidad = azar.choice(unidades)
                metodo = 'efectivo' if azar.random() < 0.7 else 'yape'
                momento = inicio_turno + timedelta(minutes=azar.randint(10, int(turno.horas * 60) - 20))
                total = precio * bloques
                venta = Venta(fecha=momento, total=total, tipo_pago=metodo, estado='pagada',
                              origen='presencial', id_usuario=cajero.id_usuario, id_sucursal=cajero.id_sucursal)
                detalle = DetalleVenta(id_flota=unidad.id_flota, precio=precio, cantidad=bloques,
                                       minutos=bloques * minutos_bloque, subtotal=total, fecha_servicio=dia)
                venta.detalles.append(detalle)
                db.session.add(venta)
                db.session.flush()
                real = bloques * minutos_bloque + (azar.choice([-6, 4]) if azar.random() < 0.05 else 0)
                cuenta_minutos = unidad.tipo_contador == 'minutos'
                delta = real if cuenta_minutos else 1
                db.session.add(RegistroUso(id_detalle_venta=detalle.id_detalle_venta, id_flota=unidad.id_flota,
                                           id_sucursal=cajero.id_sucursal, id_usuario=cajero.id_usuario,
                                           hora_inicio=momento, hora_fin=momento + timedelta(minutes=real),
                                           minutos_usados=real, estado='finalizado',
                                           minutos_previstos=bloques * minutos_bloque,
                                           hora_fin_prevista=momento + timedelta(minutes=bloques * minutos_bloque),
                                           finalizado_por='automatico', contador_delta=delta,
                                           contador_fecha=momento + timedelta(minutes=real if cuenta_minutos else 0)))
                unidad.contador_sistema = (unidad.contador_sistema or 0) + delta
                acumulado = por_unidad.setdefault(unidad.id_flota, {'sistema': 0, 'vendido': 0})
                acumulado['sistema'] += delta
                acumulado['vendido'] += bloques * minutos_bloque if cuenta_minutos else 1
                vendidos += bloques * minutos_bloque
                usados += real
                if metodo == 'efectivo':
                    efectivo += total
                    db.session.add(MovimientoCaja(tipo='ingreso', monto=total, fecha=momento, origen='venta',
                                                  descripcion=f'Venta #{venta.id_venta}', id_caja=caja.id_caja))
                else:
                    yape += total
            esperado = Decimal('50.00') + efectivo
            faltante = Decimal('-5.00') if azar.random() < 0.06 else Decimal('0')
            # Lectura manual de cada atraccion: sale del contador fisico (con algun descuadre ocasional)
            tolerancias = servicio_lecturas.obtener_tolerancias()
            for u in unidades:
                datos = por_unidad.get(u.id_flota, {'sistema': 0, 'vendido': 0})
                fisico = datos['sistema']
                if azar.random() < 0.05:
                    fisico += azar.choice([-9, 8]) if u.tipo_contador == 'minutos' else azar.choice([1, 2])
                fisico = max(fisico, 0)
                inicial = u.lectura_manual if u.lectura_manual is not None else 0
                r = servicio_lecturas.evaluar(u.tipo_contador, inicial, inicial + fisico, datos['sistema'],
                                              datos['vendido'], tolerancias)
                db.session.add(LecturaCaja(
                    id_caja=caja.id_caja, id_flota=u.id_flota, tipo_contador=u.tipo_contador, lectura_inicial=inicial,
                    sugerida=inicial, lectura_final=inicial + fisico, uso_real=r['uso_real'],
                    contador_sistema=r['contador_sistema'], vendido=r['vendido'], dif_sistema=r['dif_sistema'],
                    dif_vendido=r['dif_vendido'], alerta=r['alerta'], alertas=' | '.join(r['textos']) or None))
                u.lectura_manual = inicial + fisico
            caja.efectivo_esperado = esperado
            caja.monto_final = esperado + faltante
            caja.diferencia = faltante
            caja.total_efectivo, caja.total_yape = efectivo, yape
            caja.minutos_vendidos, caja.minutos_usados = vendidos, usados
    print(f'[seed] Historial de demostración creado ({dias} días).')


def _mostrar_credenciales(clave):
    print('\n=== Cuentas de prueba (contraseña de todas: %s) ===' % clave)
    print(f'  Administrador : {ADMIN_CORREO}')
    for u in Usuario.query.join(Cajero).order_by(Usuario.correo):
        c = u.cajero
        print(f'  Cajero        : {u.correo}  ({u.nombre_completo}, {c.tipo_turno}, {c.sucursal.nombre})')
    for u in Usuario.query.join(Cliente).order_by(Usuario.correo):
        print(f'  Cliente       : {u.correo}  (DNI {u.cliente.dni})')
    print()
