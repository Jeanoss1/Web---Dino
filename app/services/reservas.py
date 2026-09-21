import hashlib
import os
import uuid
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from app.database import db
from app.models.Cliente import Cliente
from app.models.ComprobanteReserva import ComprobanteReserva
from app.models.DetalleReserva import DetalleReserva
from app.models.Flota import Flota
from app.models.Franja import Franja
from app.models.Reserva import Reserva
from app.services import ventas
from app.services import validadores as v
from app.services.errores import ErrorNegocio
from app.services.tarifas import tarifa_vigente

MAX_ITEMS = 10
ESTADOS_CAJA = ('pago_en_revision', 'confirmada', 'rechazada')


# ------------------------------------------------------------------ utilidades
def _liberar(reserva):
    """Libera las franjas de la reserva (cancelada, rechazada o vencida)."""
    for d in reserva.detalles:
        if d.activo:
            d.activo = False
            if d.franja.estado == 'reservada':
                d.franja.estado = 'disponible'


def expirar_pendientes():
    """Cancela las reservas que no se pagaron dentro del plazo."""
    vencidas = Reserva.query.filter(
        Reserva.estado == 'pendiente_pago', Reserva.vence_en < datetime.now()
    ).all()
    for r in vencidas:
        r.estado = 'cancelada'
        _liberar(r)
    if vencidas:
        db.session.commit()
    return len(vencidas)


def _extension_por_firma(cabecera):
    """Detecta el tipo real de imagen por su contenido (no por el nombre)."""
    if cabecera.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if cabecera.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if cabecera[:4] == b'RIFF' and cabecera[8:12] == b'WEBP':
        return 'webp'
    return None


def cliente_de(usuario):
    cliente = Cliente.query.filter_by(id_usuario=usuario.id_usuario).first()
    if cliente is None:
        raise ErrorNegocio('Tu usuario no tiene un cliente asociado.', 404)
    return cliente


def _reserva_del_cliente(cliente, id_reserva):
    reserva = db.session.get(Reserva, id_reserva)
    if reserva is None or reserva.id_cliente != cliente.id_cliente:
        raise ErrorNegocio('Reserva no encontrada.', 404)
    return reserva


def _reserva_en_alcance(id_reserva, alcance):
    """`alcance` es la sede del cajero (o None para el administrador)."""
    reserva = db.session.get(Reserva, id_reserva)
    if reserva is None or (alcance is not None and reserva.id_sucursal != alcance):
        raise ErrorNegocio('Reserva no encontrada.', 404)
    return reserva


# ---------------------------------------------------------------- serialización
def comprobante_a_dict(c):
    return {
        'id_comprobante': c.id_comprobante,
        'estado': c.estado,
        'monto': float(c.monto),
        'fecha_subida': c.fecha_subida.isoformat(),
        'motivo_rechazo': c.motivo_rechazo,
        'fecha_validacion': c.fecha_validacion.isoformat() if c.fecha_validacion else None,
        'validado_por': c.validador.nombre_completo if c.id_validador and c.validador else None,
        'url': f'/comprobantes/{c.id_comprobante}',
    }


def reserva_a_dict(r, con_cliente=False):
    ultimo = r.comprobantes[-1] if r.comprobantes else None
    datos = {
        'id_reserva': r.id_reserva,
        'fecha_reserva': r.fecha_reserva.isoformat() if r.fecha_reserva else None,
        'estado': r.estado,
        'cantidad_personas': r.cantidad_personas,
        'total': float(r.total or 0),
        'sede': r.sucursal.nombre if r.sucursal else None,
        'vence_en': r.vence_en.isoformat() if r.vence_en else None,
        'detalles': [
            {
                'unidad': d.flota.nombre,
                'inicio': d.franja.horario_inicio.isoformat(),
                'fin': d.franja.horario_fin.isoformat(),
            }
            for d in r.detalles
        ],
        'comprobante': comprobante_a_dict(ultimo) if ultimo else None,
    }
    if con_cliente:
        datos['cliente'] = {
            'nombre': f'{r.cliente.nombre} {r.cliente.apellido}',
            'dni': r.cliente.dni,
            'telefono': r.cliente.telefono,
        }
    return datos


# ------------------------------------------------------------------ del cliente
def crear_reserva(cliente, datos):
    """datos = {"cantidad_personas": 2, "items": [{"id_flota": 1, "id_franja": 3}]}"""
    items = datos.get('items')
    if not isinstance(items, list) or not items:
        raise ErrorNegocio('Debes indicar al menos una atracción y un horario.')
    if len(items) > MAX_ITEMS:
        raise ErrorNegocio(f'Máximo {MAX_ITEMS} horarios por reserva.')
    personas = v.entero(datos.get('cantidad_personas', 1), 'cantidad de personas', 1, 20)

    expirar_pendientes()
    ids = []
    for item in items:
        if not isinstance(item, dict):
            raise ErrorNegocio('Formato de items no válido.')
        ids.append(v.entero(item.get('id_franja'), 'id_franja', 1, 10**9))
    if len(set(ids)) != len(ids):
        raise ErrorNegocio('No repitas el mismo horario en la reserva.')

    # Bloquea las filas para que dos clientes no tomen la misma franja a la vez
    franjas = (
        Franja.query.filter(Franja.id_franja.in_(ids)).order_by(Franja.id_franja)
        .with_for_update().all()
    )
    if len(franjas) != len(ids):
        raise ErrorNegocio('Alguno de los horarios no existe.', 404)

    ahora = datetime.now()
    sedes = set()
    for franja, item in zip(sorted(franjas, key=lambda f: ids.index(f.id_franja)), items):
        unidad = franja.flota
        if item.get('id_flota') not in (None, unidad.id_flota):
            raise ErrorNegocio('El horario no corresponde a esa atracción.')
        if unidad.estado != 'disponible':
            raise ErrorNegocio(f'{unidad.nombre} no está disponible.')
        if franja.estado != 'disponible' or franja.horario_inicio < ahora:
            raise ErrorNegocio(f'{unidad.nombre} ya no está disponible en ese horario.')
        sedes.add(unidad.id_sucursal)
    if len(sedes) != 1:
        raise ErrorNegocio('Todos los horarios deben ser de la misma sede.')

    tarifa = tarifa_vigente()
    reserva = Reserva(
        id_cliente=cliente.id_cliente, id_sucursal=sedes.pop(), estado='pendiente_pago',
        cantidad_personas=personas, total=tarifa.precio * len(franjas),
        vence_en=ahora + timedelta(minutes=current_app.config['MINUTOS_LIMITE_PAGO']),
    )
    db.session.add(reserva)
    for franja in franjas:
        franja.estado = 'reservada'
        reserva.detalles.append(DetalleReserva(id_flota=franja.id_flota, id_franja=franja.id_franja))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ErrorNegocio('Otro cliente acaba de reservar ese horario. Elige otro.')
    return reserva


def subir_comprobante(cliente, id_reserva, archivo):
    """Recibe la captura del pago Yape (multipart, campo 'comprobante')."""
    expirar_pendientes()
    reserva = _reserva_del_cliente(cliente, id_reserva)
    if reserva.estado == 'pago_en_revision':
        raise ErrorNegocio('Ya enviaste un comprobante; el cajero lo está revisando.')
    if reserva.estado != 'pendiente_pago':
        raise ErrorNegocio('Esta reserva ya no admite comprobantes.')

    if archivo is None or not archivo.filename:
        raise ErrorNegocio('Selecciona la captura de tu pago.')
    contenido = archivo.read()
    if not contenido:
        raise ErrorNegocio('El archivo está vacío.')
    if len(contenido) > current_app.config['MAX_CONTENT_LENGTH']:
        raise ErrorNegocio('La imagen supera los 5 MB.', 413)
    extension = _extension_por_firma(contenido[:16])
    if extension is None:
        raise ErrorNegocio('Sube una imagen PNG, JPG o WEBP.')

    huella = hashlib.sha256(contenido).hexdigest()
    repetido = ComprobanteReserva.query.filter(
        ComprobanteReserva.hash_archivo == huella,
        ComprobanteReserva.id_reserva != reserva.id_reserva,
        ComprobanteReserva.estado.in_(['por_validar', 'aceptado']),
    ).first()
    if repetido:
        raise ErrorNegocio('Esta captura ya fue usada en otra reserva.')

    # El nombre lo generamos nosotros: nunca se usa el que envía el usuario
    carpeta = current_app.config['UPLOAD_FOLDER']
    os.makedirs(carpeta, exist_ok=True)
    nombre = f'reserva{reserva.id_reserva}_{uuid.uuid4().hex}.{extension}'
    ruta = os.path.join(carpeta, nombre)
    with open(ruta, 'wb') as f:
        f.write(contenido)
    try:
        db.session.add(ComprobanteReserva(
            id_reserva=reserva.id_reserva, metodo_pago='yape', monto=reserva.total,
            archivo=nombre, hash_archivo=huella, estado='por_validar',
        ))
        reserva.estado = 'pago_en_revision'
        reserva.vence_en = None
        db.session.commit()
    except Exception:
        db.session.rollback()
        os.remove(ruta)
        raise
    return reserva


def cancelar(cliente, id_reserva):
    reserva = _reserva_del_cliente(cliente, id_reserva)
    if reserva.estado != 'pendiente_pago':
        raise ErrorNegocio('Solo se puede cancelar una reserva pendiente de pago.')
    reserva.estado = 'cancelada'
    _liberar(reserva)
    db.session.commit()
    return reserva


def listar_del_cliente(cliente):
    expirar_pendientes()
    return sorted(cliente.reservas, key=lambda r: r.id_reserva, reverse=True)


def comprobante_visible(id_comprobante, usuario, alcance):
    """Devuelve el comprobante solo si es del cliente dueño o del personal de la sede."""
    comprobante = db.session.get(ComprobanteReserva, id_comprobante)
    if comprobante is None:
        raise ErrorNegocio('Comprobante no encontrado.', 404)
    reserva = comprobante.reserva
    if usuario.rol_nombre == 'cliente':
        propio = usuario.cliente is not None and reserva.id_cliente == usuario.cliente.id_cliente
        if not propio:
            raise ErrorNegocio('Comprobante no encontrado.', 404)
    elif alcance is not None and reserva.id_sucursal != alcance:
        raise ErrorNegocio('Comprobante no encontrado.', 404)
    return comprobante


# ------------------------------------------------------------------- del cajero
def listar_para_caja(alcance, estado):
    if estado not in ESTADOS_CAJA:
        raise ErrorNegocio("El estado debe ser 'pago_en_revision', 'confirmada' o 'rechazada'.")
    expirar_pendientes()
    consulta = Reserva.query.filter_by(estado=estado)
    if alcance is not None:
        consulta = consulta.filter_by(id_sucursal=alcance)
    orden = Reserva.id_reserva.asc() if estado == 'pago_en_revision' else Reserva.id_reserva.desc()
    return consulta.order_by(orden).limit(100).all()


def _comprobante_por_validar(reserva):
    if reserva.estado != 'pago_en_revision':
        return None
    return next((c for c in reversed(reserva.comprobantes) if c.estado == 'por_validar'), None)


def aceptar(id_reserva, validador, alcance):
    """Acepta el pago: la reserva queda confirmada y se registra la venta."""
    reserva = _reserva_en_alcance(id_reserva, alcance)
    comprobante = _comprobante_por_validar(reserva)
    if comprobante is None:
        raise ErrorNegocio('Esta reserva no tiene un comprobante por validar.')
    comprobante.estado = 'aceptado'
    comprobante.id_validador = validador.id_usuario
    comprobante.fecha_validacion = datetime.now()
    reserva.estado = 'confirmada'
    ventas.registrar_venta_reserva(reserva, validador)
    db.session.commit()
    return reserva


def rechazar(id_reserva, validador, alcance, motivo):
    """Rechaza el pago con un motivo. La reserva queda rechazada y libera sus horarios."""
    reserva = _reserva_en_alcance(id_reserva, alcance)
    comprobante = _comprobante_por_validar(reserva)
    if comprobante is None:
        raise ErrorNegocio('Esta reserva no tiene un comprobante por validar.')
    motivo = v.texto(motivo, 'motivo del rechazo', 3, 200)
    comprobante.estado = 'rechazado'
    comprobante.motivo_rechazo = motivo
    comprobante.id_validador = validador.id_usuario
    comprobante.fecha_validacion = datetime.now()
    reserva.estado = 'rechazada'
    _liberar(reserva)
    db.session.commit()
    return reserva
