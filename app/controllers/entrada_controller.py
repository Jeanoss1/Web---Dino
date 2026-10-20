"""Entrada por tiempo (Hoyos Rubio y sedes futuras del mismo modelo).

A diferencia de Real Plaza/Mega Plaza (flota + turno fijo), aquí se vende
entrada a una zona por un tiempo determinado, con paquetes de precio por
niño (reserva_controller.py / comprobante_controller.py / venta_controller.py
NO se tocan: este archivo es un flujo paralelo, no un reemplazo).

Dos formas de vender una entrada:
  - En caja, pago inmediato: crear_venta_entrada() + el ya existente
    POST /api/ventas/<id>/pago de venta_controller.py.
  - Reserva online con comprobante Yape: crear_reserva_entrada() + subir
    comprobante + el cajero la valida (como las reservas de flota, pero en
    una cola separada).
"""

import hashlib
import os
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from flask import (
    Blueprint, current_app, jsonify, render_template, request,
    send_from_directory, session
)

from app.controllers.decoradores import login_requerido, rol_requerido
from app.controllers.venta_controller import _venta_a_dict
from app.database import db

from app.models.Cliente import Cliente
from app.models.ComprobanteReservaEntrada import ComprobanteReservaEntrada
from app.models.DetalleReservaEntrada import DetalleReservaEntrada
from app.models.DetalleVenta import DetalleVenta
from app.models.PaqueteTarifa import PaqueteTarifa
from app.models.ReservaEntrada import ReservaEntrada
from app.models.Sucursal import Sucursal
from app.models.Venta import Venta
from app.models.Zona import Zona

from app.servicios_entrada import ErrorPaquete, calcular_subtotal_paquete


entrada_bp = Blueprint('entrada', __name__)

ROLES_CAJA = ('administrador', 'cajero')


# ============================================================
# PÁGINA PÚBLICA
# ============================================================

@entrada_bp.route('/sedes/hoyos-rubio')
def pagina_hoyos_rubio():
    sede = Sucursal.query.filter_by(nombre='Hoyos Rubio').first()

    zonas = []
    if sede:
        zonas = [
            {
                'zona': z,
                'paquetes': [p for p in z.paquetes if p.estado == 'activa'],
            }
            for z in Zona.query.filter_by(
                id_sucursal=sede.id_sucursal, estado='activa'
            ).order_by(Zona.id_zona).all()
        ]

    return render_template('sede_hoyos_rubio.html', sede=sede, zonas=zonas)


@entrada_bp.route('/caja/entradas')
@rol_requerido(*ROLES_CAJA)
def pagina_caja_entradas():
    return render_template('caja_entradas.html')


# ============================================================
# CATÁLOGO (genérico: sirve para cualquier sede de este modelo)
# ============================================================

@entrada_bp.route('/api/sedes/<int:id_sucursal>/zonas')
def listar_zonas(id_sucursal):
    zonas = (
        Zona.query
        .filter_by(id_sucursal=id_sucursal, estado='activa')
        .order_by(Zona.id_zona)
        .all()
    )
    return jsonify([
        {
            'id_zona': z.id_zona,
            'nombre': z.nombre,
            'descripcion': z.descripcion,
            'paquetes': [
                {
                    'id_paquete': p.id_paquete,
                    'nombre': p.nombre,
                    'tipo': p.tipo,
                    'duracion_minutos': p.duracion_minutos,
                    'precio': float(p.precio),
                    'es_por_ninio': p.es_por_ninio,
                    'minimo_cantidad': p.minimo_cantidad,
                }
                for p in z.paquetes if p.estado == 'activa'
            ],
        }
        for z in zonas
    ])


@entrada_bp.route('/api/sedes/con-entradas')
@rol_requerido(*ROLES_CAJA)
def listar_sedes_con_entradas():
    """Solo las sedes que de verdad venden entrada por tiempo (tienen al
    menos una zona activa) -- para el selector de 'Vender Entradas' en caja,
    que no debe listar Real Plaza/Mega Plaza."""
    ids = {z.id_sucursal for z in Zona.query.filter_by(estado='activa').all()}
    sedes = Sucursal.query.filter(Sucursal.id_sucursal.in_(ids)).order_by(Sucursal.nombre).all()
    return jsonify([
        {'id_sucursal': s.id_sucursal, 'nombre': s.nombre, 'direccion': s.direccion}
        for s in sedes
    ])


# ============================================================
# UTILIDADES
# ============================================================

def _cliente_actual():
    return Cliente.query.filter_by(correo=session.get('correo')).first()


def _es_personal():
    return session.get('rol') in ROLES_CAJA


def _extension_por_firma(cabecera):
    """Detecta el tipo real de imagen por su contenido (no por el nombre)."""
    if cabecera.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if cabecera.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return 'webp'
    return None


def _detalles_entrada(r):
    return [
        {
            'id_paquete': d.id_paquete,
            'paquete': d.paquete.nombre,
            'cantidad': d.cantidad,
            'subtotal': float(d.subtotal),
        }
        for d in r.detalles
    ]


def _comprobante_entrada_a_dict(c):
    return {
        'id_comprobante': c.id_comprobante,
        'estado': c.estado,
        'monto': float(c.monto),
        'fecha_subida': c.fecha_subida.isoformat(),
        'motivo_rechazo': c.motivo_rechazo,
        'url': f'/comprobantes-entrada/{c.id_comprobante}',
    }


def _reserva_entrada_a_dict(r, con_cliente=False):
    ultimo = r.comprobantes[-1] if r.comprobantes else None
    datos = {
        'id_reserva_entrada': r.id_reserva_entrada,
        'id_sucursal': r.id_sucursal,
        'fecha_reserva': r.fecha_reserva.isoformat() if r.fecha_reserva else None,
        'estado': r.estado,
        'total': float(r.total or 0),
        'detalles': _detalles_entrada(r),
        'comprobante': _comprobante_entrada_a_dict(ultimo) if ultimo else None,
    }
    if con_cliente:
        datos['cliente'] = {
            'nombre': f'{r.cliente.nombre} {r.cliente.apellido}',
            'dni': r.cliente.dni,
            'telefono': r.cliente.telefono,
        }
    return datos


# ============================================================
# RESERVA ONLINE (cliente)
# ============================================================

@entrada_bp.route('/api/reservas-entrada', methods=['POST'])
@login_requerido
def crear_reserva_entrada():
    """
    Body JSON:

    {
        "id_sucursal": 3,
        "items": [
            {"id_paquete": 1, "cantidad": 2, "nino_hasta_5": true}
        ]
    }
    """

    datos = request.get_json(silent=True) or {}
    id_sucursal = datos.get('id_sucursal')
    items = datos.get('items') or []

    if not id_sucursal or not items:
        return jsonify(error='Indica la sede y al menos un paquete'), 400

    cliente = _cliente_actual()

    if cliente is None:
        return jsonify(error='Tu usuario no tiene un cliente asociado'), 404

    try:
        if any(
            not isinstance(item, dict)
            or not item.get('id_paquete')
            or not item.get('cantidad')
            for item in items
        ):
            raise ErrorPaquete('Cada item necesita id_paquete y cantidad')

        reserva = ReservaEntrada(
            id_cliente=cliente.id_cliente,
            id_sucursal=id_sucursal,
            estado='pendiente',
        )
        db.session.add(reserva)

        total = Decimal('0')

        for item in items:
            paquete = db.session.get(PaqueteTarifa, item['id_paquete'])

            if (
                paquete is None
                or paquete.estado != 'activa'
                or paquete.zona.id_sucursal != int(id_sucursal)
            ):
                raise ErrorPaquete('El paquete no existe o no pertenece a esa sede')

            cantidad = int(item['cantidad'])
            subtotal = calcular_subtotal_paquete(
                paquete, cantidad, nino_hasta_5=item.get('nino_hasta_5')
            )

            reserva.detalles.append(
                DetalleReservaEntrada(
                    id_paquete=paquete.id_paquete,
                    cantidad=cantidad,
                    subtotal=subtotal,
                )
            )

            total += Decimal(str(subtotal))

        reserva.total = total
        db.session.commit()

    except (ErrorPaquete, ValueError, TypeError) as e:
        db.session.rollback()
        return jsonify(error=str(e)), 400

    return jsonify(_reserva_entrada_a_dict(reserva)), 201


@entrada_bp.route('/api/reservas-entrada/mis')
@login_requerido
def mis_reservas_entrada():
    cliente = _cliente_actual()

    if cliente is None:
        return jsonify([])

    reservas = (
        ReservaEntrada.query
        .filter_by(id_cliente=cliente.id_cliente)
        .order_by(ReservaEntrada.id_reserva_entrada.desc())
        .all()
    )

    return jsonify([_reserva_entrada_a_dict(r) for r in reservas])


@entrada_bp.route('/api/reservas-entrada/<int:id_reserva_entrada>')
@login_requerido
def ver_reserva_entrada(id_reserva_entrada):
    reserva = db.session.get(ReservaEntrada, id_reserva_entrada)
    cliente = _cliente_actual()

    es_dueno = (
        cliente is not None
        and reserva is not None
        and reserva.id_cliente == cliente.id_cliente
    )

    if reserva is None or not (es_dueno or _es_personal()):
        return jsonify(error='Reserva no encontrada'), 404

    return jsonify(_reserva_entrada_a_dict(reserva, con_cliente=_es_personal()))


@entrada_bp.route(
    '/api/reservas-entrada/<int:id_reserva_entrada>/cancelar', methods=['POST']
)
@login_requerido
def cancelar_reserva_entrada(id_reserva_entrada):
    reserva = db.session.get(ReservaEntrada, id_reserva_entrada)
    cliente = _cliente_actual()

    es_dueno = (
        cliente is not None
        and reserva is not None
        and reserva.id_cliente == cliente.id_cliente
    )

    if reserva is None or not (es_dueno or _es_personal()):
        return jsonify(error='Reserva no encontrada'), 404

    if reserva.estado == 'cancelada':
        return jsonify(error='La reserva ya estaba cancelada'), 400

    reserva.estado = 'cancelada'
    db.session.commit()

    return jsonify(_reserva_entrada_a_dict(reserva))


@entrada_bp.route(
    '/api/reservas-entrada/<int:id_reserva_entrada>/comprobante', methods=['POST']
)
@login_requerido
def subir_comprobante_entrada(id_reserva_entrada):
    """Recibe la captura del pago (multipart/form-data, campo 'comprobante')."""
    reserva = db.session.get(ReservaEntrada, id_reserva_entrada)
    cliente = _cliente_actual()

    if (
        reserva is None
        or cliente is None
        or reserva.id_cliente != cliente.id_cliente
    ):
        return jsonify(error='Reserva no encontrada'), 404

    if reserva.estado == 'cancelada':
        return jsonify(error='Esta reserva fue cancelada'), 400
    if reserva.estado == 'confirmada':
        return jsonify(error='Esta reserva ya está confirmada'), 400
    if reserva.estado == 'por_validar':
        return jsonify(error='Ya enviaste un comprobante, el cajero lo está revisando'), 400

    archivo = request.files.get('comprobante')
    if archivo is None or not archivo.filename:
        return jsonify(error='Selecciona la captura de tu pago'), 400

    contenido = archivo.read()
    if not contenido:
        return jsonify(error='El archivo está vacío'), 400

    extension = _extension_por_firma(contenido[:16])
    if extension is None:
        return jsonify(error='Sube una imagen PNG, JPG o WEBP'), 400

    huella = hashlib.sha256(contenido).hexdigest()
    repetido = (
        ComprobanteReservaEntrada.query
        .filter(
            ComprobanteReservaEntrada.hash_archivo == huella,
            ComprobanteReservaEntrada.id_reserva_entrada != reserva.id_reserva_entrada,
            ComprobanteReservaEntrada.estado.in_(['por_validar', 'aceptado']),
        )
        .first()
    )
    if repetido:
        return jsonify(error='Esta captura ya fue usada en otra reserva'), 400

    carpeta = current_app.config['UPLOAD_FOLDER']
    os.makedirs(carpeta, exist_ok=True)
    nombre = f'entrada{reserva.id_reserva_entrada}_{uuid.uuid4().hex}.{extension}'
    with open(os.path.join(carpeta, nombre), 'wb') as f:
        f.write(contenido)

    comprobante = ComprobanteReservaEntrada(
        id_reserva_entrada=reserva.id_reserva_entrada, metodo_pago='yape',
        monto=reserva.total, archivo=nombre, hash_archivo=huella,
        estado='por_validar',
    )
    reserva.estado = 'por_validar'
    db.session.add(comprobante)
    db.session.commit()

    return jsonify(_reserva_entrada_a_dict(reserva)), 201


@entrada_bp.route('/comprobantes-entrada/<int:id_comprobante>')
@login_requerido
def ver_comprobante_entrada(id_comprobante):
    """Solo lo ve el dueño de la reserva o el personal de caja."""
    comprobante = db.session.get(ComprobanteReservaEntrada, id_comprobante)
    if comprobante is None:
        return jsonify(error='Comprobante no encontrado'), 404

    cliente = _cliente_actual()
    es_dueno = (
        cliente is not None
        and comprobante.reserva_entrada.id_cliente == cliente.id_cliente
    )

    if not (es_dueno or _es_personal()):
        return jsonify(error='Comprobante no encontrado'), 404

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], comprobante.archivo)


# ============================================================
# COLA DE VALIDACIÓN DEL CAJERO (paralela a la de flota/turno)
# ============================================================

def _comprobante_entrada_por_validar(reserva):
    if reserva is None or reserva.estado != 'por_validar':
        return None
    for c in reversed(reserva.comprobantes):
        if c.estado == 'por_validar':
            return c
    return None


@entrada_bp.route('/api/caja/reservas-entrada')
@rol_requerido(*ROLES_CAJA)
def listar_reservas_entrada_caja():
    """?estado=por_validar (por defecto) | confirmada"""
    estado = request.args.get('estado', 'por_validar')
    if estado not in ('por_validar', 'confirmada'):
        return jsonify(error="El estado debe ser 'por_validar' o 'confirmada'"), 400

    orden = (
        ReservaEntrada.id_reserva_entrada.asc()
        if estado == 'por_validar'
        else ReservaEntrada.id_reserva_entrada.desc()
    )

    reservas = (
        ReservaEntrada.query.filter_by(estado=estado)
        .order_by(orden).limit(100).all()
    )

    return jsonify([_reserva_entrada_a_dict(r, con_cliente=True) for r in reservas])


@entrada_bp.route(
    '/api/reservas-entrada/<int:id_reserva_entrada>/aceptar', methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def aceptar_reserva_entrada(id_reserva_entrada):
    reserva = db.session.get(ReservaEntrada, id_reserva_entrada)
    comprobante = _comprobante_entrada_por_validar(reserva)
    if comprobante is None:
        return jsonify(error='Esta reserva no tiene un comprobante por validar'), 400

    comprobante.estado = 'aceptado'
    comprobante.id_validador = session['id_usuario']
    comprobante.fecha_validacion = datetime.now()
    reserva.estado = 'confirmada'
    db.session.commit()

    return jsonify(_reserva_entrada_a_dict(reserva, con_cliente=True))


@entrada_bp.route(
    '/api/reservas-entrada/<int:id_reserva_entrada>/rechazar', methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def rechazar_reserva_entrada(id_reserva_entrada):
    """Body JSON: {"motivo": "El monto no coincide"}."""
    reserva = db.session.get(ReservaEntrada, id_reserva_entrada)
    comprobante = _comprobante_entrada_por_validar(reserva)
    if comprobante is None:
        return jsonify(error='Esta reserva no tiene un comprobante por validar'), 400

    datos = request.get_json(silent=True) or {}
    motivo = (datos.get('motivo') or '').strip()
    if not motivo:
        return jsonify(error='Indica el motivo del rechazo'), 400

    comprobante.estado = 'rechazado'
    comprobante.motivo_rechazo = motivo[:200]
    comprobante.id_validador = session['id_usuario']
    comprobante.fecha_validacion = datetime.now()
    reserva.estado = 'pendiente'
    db.session.commit()

    return jsonify(_reserva_entrada_a_dict(reserva, con_cliente=True))


@entrada_bp.route(
    '/api/reservas-entrada/<int:id_reserva_entrada>/marcar-ingreso', methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def marcar_ingreso_reserva_entrada(id_reserva_entrada):
    """El cliente reservó y pagó online; esto marca que ya entró físicamente
    a la zona, que es cuando arranca su temporizador."""
    reserva = db.session.get(ReservaEntrada, id_reserva_entrada)
    if reserva is None or reserva.estado != 'confirmada':
        return jsonify(error='Esta reserva no está confirmada'), 400

    ahora = datetime.now()
    for detalle in reserva.detalles:
        if detalle.hora_inicio is None:
            detalle.hora_inicio = ahora

    db.session.commit()
    return jsonify(_reserva_entrada_a_dict(reserva))


# ============================================================
# VENTA EN CAJA (pago inmediato, igual que las otras sedes)
# ============================================================

@entrada_bp.route('/api/ventas/entradas', methods=['POST'])
@rol_requerido(*ROLES_CAJA)
def crear_venta_entrada():
    """
    Body JSON:

    {
        "id_sucursal": 3,
        "items": [
            {"id_paquete": 1, "cantidad": 2, "nino_hasta_5": true}
        ]
    }

    Crea la venta con el precio ya calculado por el servidor y arranca el
    temporizador de inmediato (es venta en el momento: el niño entra ya).
    El cobro se hace después con el endpoint existente
    POST /api/ventas/<id>/pago (venta_controller.py, sin modificar).
    """

    datos = request.get_json(silent=True) or {}
    id_sucursal = datos.get('id_sucursal')
    items = datos.get('items') or []

    if not id_sucursal or not items:
        return jsonify(error='Indica la sede y al menos un paquete'), 400

    ahora = datetime.now()
    venta = Venta(
        id_usuario=session['id_usuario'],
        id_sucursal=id_sucursal,
        estado='pendiente',
    )

    total = Decimal('0')

    try:
        if any(
            not isinstance(item, dict)
            or not item.get('id_paquete')
            or not item.get('cantidad')
            for item in items
        ):
            raise ErrorPaquete('Cada item necesita id_paquete y cantidad')

        for item in items:
            paquete = db.session.get(PaqueteTarifa, item['id_paquete'])

            if (
                paquete is None
                or paquete.estado != 'activa'
                or paquete.zona.id_sucursal != int(id_sucursal)
            ):
                raise ErrorPaquete('El paquete no existe o no pertenece a esa sede')

            cantidad = int(item['cantidad'])
            subtotal = calcular_subtotal_paquete(
                paquete, cantidad, nino_hasta_5=item.get('nino_hasta_5')
            )

            detalle = DetalleVenta(
                precio=paquete.precio,
                cantidad=cantidad if paquete.es_por_ninio else 1,
                subtotal=subtotal,
                id_paquete=paquete.id_paquete,
                hora_inicio=ahora,
            )

            venta.detalles.append(detalle)
            total += Decimal(str(subtotal))

    except (ErrorPaquete, ValueError, TypeError) as e:
        return jsonify(error=str(e)), 400

    venta.total = total
    db.session.add(venta)
    db.session.commit()

    return jsonify(_venta_a_dict(venta)), 201


# ============================================================
# TEMPORIZADOR: ENTRADAS ACTIVAS EN CAJA
# ============================================================

def _entrada_activa_a_dict(tipo, detalle):
    return {
        'tipo': tipo,  # 'venta' (en caja) o 'reserva' (online ya validada)
        'id': detalle.id_detalle_venta if tipo == 'venta' else detalle.id_detalle,
        'paquete': detalle.paquete.nombre,
        'duracion_minutos': detalle.paquete.duracion_minutos,
        'hora_inicio': detalle.hora_inicio.isoformat(),
        'exceso_cobrado': bool(detalle.exceso_cobrado),
    }


@entrada_bp.route('/api/caja/entradas-activas')
@rol_requerido(*ROLES_CAJA)
def listar_entradas_activas():
    """Entradas con el temporizador corriendo (venta en caja ya pagada, o
    reserva online ya confirmada y con ingreso marcado). El frontend calcula
    la cuenta regresiva con duracion_minutos + hora_inicio."""
    limite = datetime.now() - timedelta(hours=6)

    detalles_venta = (
        DetalleVenta.query
        .join(Venta)
        .filter(
            DetalleVenta.hora_inicio.isnot(None),
            DetalleVenta.hora_inicio >= limite,
            DetalleVenta.hora_fin.is_(None),
            DetalleVenta.id_paquete.isnot(None),
            Venta.estado == 'pagada',
        )
        .all()
    )

    detalles_reserva = (
        DetalleReservaEntrada.query
        .join(ReservaEntrada)
        .filter(
            DetalleReservaEntrada.hora_inicio.isnot(None),
            DetalleReservaEntrada.hora_inicio >= limite,
            DetalleReservaEntrada.hora_fin.is_(None),
            ReservaEntrada.estado == 'confirmada',
        )
        .all()
    )

    activas = (
        [_entrada_activa_a_dict('venta', d) for d in detalles_venta]
        + [_entrada_activa_a_dict('reserva', d) for d in detalles_reserva]
    )
    activas.sort(key=lambda a: a['hora_inicio'])

    return jsonify(activas)


def _detalle_y_sede(tipo, id_detalle):
    if tipo == 'venta':
        detalle = db.session.get(DetalleVenta, id_detalle)
        id_sucursal = detalle.venta.id_sucursal if detalle else None
    elif tipo == 'reserva':
        detalle = db.session.get(DetalleReservaEntrada, id_detalle)
        id_sucursal = detalle.reserva_entrada.id_sucursal if detalle else None
    else:
        return None, None, "tipo debe ser 'venta' o 'reserva'"
    return detalle, id_sucursal, None


@entrada_bp.route(
    '/api/caja/entradas-activas/<tipo>/<int:id_detalle>/salida', methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def marcar_salida_entrada(tipo, id_detalle):
    """El niño salió a tiempo, sin cargo adicional. Registra la hora real de
    salida para el cuadre de minutos (vendidos vs usados)."""
    detalle, _id_sucursal, error = _detalle_y_sede(tipo, id_detalle)
    if error:
        return jsonify(error=error), 400
    if detalle is None:
        return jsonify(error='Entrada no encontrada'), 404
    if detalle.hora_fin is not None:
        return jsonify(error='Esta entrada ya registra una salida'), 400

    detalle.hora_fin = datetime.now()
    db.session.commit()
    return jsonify(ok=True)


@entrada_bp.route(
    '/api/caja/entradas-activas/<tipo>/<int:id_detalle>/adicional', methods=['POST']
)
@rol_requerido(*ROLES_CAJA)
def cobrar_adicional(tipo, id_detalle):
    """Cobra el monto adicional configurado por el administrador cuando el
    niño no sale cuando se le llama. Body JSON opcional:
    {"metodo_pago": "efectivo"}."""

    detalle, id_sucursal, error = _detalle_y_sede(tipo, id_detalle)
    if error:
        return jsonify(error=error), 400

    if detalle is None:
        return jsonify(error='Entrada no encontrada'), 404
    if detalle.exceso_cobrado:
        return jsonify(error='El adicional ya fue cobrado para esta entrada'), 400

    sucursal = db.session.get(Sucursal, id_sucursal) if id_sucursal else None
    if sucursal is None or not sucursal.monto_adicional_exceso:
        return jsonify(error='Esta sede no tiene configurado un monto adicional'), 400

    datos = request.get_json(silent=True) or {}
    metodo = (datos.get('metodo_pago') or 'efectivo').strip()

    venta = Venta(
        id_usuario=session['id_usuario'],
        id_sucursal=id_sucursal,
        estado='pendiente',
    )
    detalle_adicional = DetalleVenta(
        precio=sucursal.monto_adicional_exceso, cantidad=1
    )
    detalle_adicional.calcular_subtotal()
    venta.detalles.append(detalle_adicional)
    venta.total = detalle_adicional.subtotal
    db.session.add(venta)
    db.session.flush()

    from app.models.Caja import Caja
    from app.models.MovimientoCaja import MovimientoCaja
    from app.models.Pago import Pago
    from app.models.Ticket import Ticket

    pago = Pago(
        monto=detalle_adicional.subtotal, metodo_pago=metodo, estado='pagado'
    )
    pago.detalle_venta = detalle_adicional
    pago.ticket = Ticket(
        codigo=f"T{datetime.now():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    )
    db.session.add(pago)
    db.session.flush()

    caja = Caja.query.filter_by(estado='abierta').first()
    if caja and metodo.lower() == 'efectivo':
        db.session.add(
            MovimientoCaja(
                tipo='ingreso',
                monto=detalle_adicional.subtotal,
                descripcion=f'Adicional por exceso de tiempo (venta {venta.id_venta})',
                id_caja=caja.id_caja,
                ticket=pago.ticket,
            )
        )

    venta.tipo_pago = metodo
    venta.estado = 'pagada'
    detalle.exceso_cobrado = True
    detalle.hora_fin = datetime.now()

    db.session.commit()

    return jsonify({
        'adicional': float(detalle_adicional.subtotal),
        'ticket': pago.ticket.codigo,
    })
