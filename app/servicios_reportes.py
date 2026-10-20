"""Reporte de ventas por sede/cajero/método de pago, para cualquier rango de
fechas (diario/semanal/mensual/personalizado).

Junta TRES orígenes de ingresos en una sola lista de transacciones, porque
`Venta` (venta de mostrador) es solo una parte del negocio: Real Plaza y Mega
Plaza venden sobre todo por `Reserva` (reserva online + comprobante Yape), y
Hoyos Rubio por `ReservaEntrada` además de `Venta`. Si el reporte solo mirara
`Venta`, Real Plaza/Mega Plaza saldrían casi vacíos.
"""

from calendar import monthrange
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.models.Reserva import Reserva
from app.models.ReservaEntrada import ReservaEntrada
from app.models.Sucursal import Sucursal
from app.models.usuario import Usuario
from app.models.Venta import Venta


class ErrorReporte(Exception):
    pass


def resolver_rango(rango, referencia=None, desde=None, hasta=None):
    """Devuelve (fecha_inicio, fecha_fin) -- ambas `date`, fin inclusivo."""

    if rango == 'personalizado':
        if not desde or not hasta:
            raise ErrorReporte('Indica desde y hasta para un rango personalizado')
        if desde > hasta:
            raise ErrorReporte('"desde" no puede ser posterior a "hasta"')
        if (hasta - desde).days > 366:
            raise ErrorReporte('El rango no puede superar 366 días')
        return desde, hasta

    ref = referencia or date.today()

    if rango == 'diario':
        return ref, ref

    if rango == 'semanal':
        inicio = ref - timedelta(days=ref.weekday())  # lunes
        return inicio, inicio + timedelta(days=6)     # domingo

    if rango == 'mensual':
        inicio = ref.replace(day=1)
        ultimo_dia = monthrange(ref.year, ref.month)[1]
        return inicio, ref.replace(day=ultimo_dia)

    raise ErrorReporte("rango debe ser 'diario', 'semanal', 'mensual' o 'personalizado'")


def _comprobante_aceptado(reserva):
    for c in reversed(reserva.comprobantes):
        if c.estado == 'aceptado':
            return c
    return None


def _transacciones(id_sucursal, inicio, fin):
    """Lista normalizada: {fecha, id_sucursal, id_cajero, metodo_pago, total}."""

    desde_dt = datetime.combine(inicio, datetime.min.time())
    hasta_dt = datetime.combine(fin + timedelta(days=1), datetime.min.time())

    filas = []

    # --- Ventas de mostrador (cualquier sede) ---
    consulta = Venta.query.filter(
        Venta.estado == 'pagada',
        Venta.fecha >= desde_dt,
        Venta.fecha < hasta_dt,
    )
    if id_sucursal:
        consulta = consulta.filter(Venta.id_sucursal == id_sucursal)

    for v in consulta.all():
        filas.append({
            'fecha': v.fecha,
            'id_sucursal': v.id_sucursal,
            'id_cajero': v.id_usuario,
            'metodo_pago': (v.tipo_pago or 'efectivo').lower(),
            'total': Decimal(str(v.total or 0)),
        })

    # --- Reservas de flota confirmadas (Real Plaza / Mega Plaza) ---
    for r in Reserva.query.filter(
        Reserva.estado == 'confirmada',
        Reserva.fecha_reserva >= desde_dt,
        Reserva.fecha_reserva < hasta_dt,
    ).all():
        if not r.detalles:
            continue
        sede = r.detalles[0].flota.id_sucursal
        if id_sucursal and sede != id_sucursal:
            continue
        comprobante = _comprobante_aceptado(r)
        filas.append({
            'fecha': r.fecha_reserva,
            'id_sucursal': sede,
            'id_cajero': comprobante.id_validador if comprobante else None,
            'metodo_pago': 'yape',
            'total': Decimal(str(r.total or 0)),
        })

    # --- Reservas de entrada por tiempo confirmadas (Hoyos Rubio) ---
    for r in ReservaEntrada.query.filter(
        ReservaEntrada.estado == 'confirmada',
        ReservaEntrada.fecha_reserva >= desde_dt,
        ReservaEntrada.fecha_reserva < hasta_dt,
    ).all():
        if id_sucursal and r.id_sucursal != id_sucursal:
            continue
        comprobante = _comprobante_aceptado(r)
        filas.append({
            'fecha': r.fecha_reserva,
            'id_sucursal': r.id_sucursal,
            'id_cajero': comprobante.id_validador if comprobante else None,
            'metodo_pago': 'yape',
            'total': Decimal(str(r.total or 0)),
        })

    return filas


def generar_reporte(id_sucursal=None, rango='semanal', referencia=None, desde=None, hasta=None):
    inicio, fin = resolver_rango(rango, referencia, desde, hasta)
    filas = _transacciones(id_sucursal, inicio, fin)

    sedes = {s.id_sucursal: s.nombre for s in Sucursal.query.all()}
    usuarios = {u.id_usuario: f'{u.nombre} {u.apellido}' for u in Usuario.query.all()}

    total_general = Decimal('0')
    por_sede = defaultdict(lambda: {'cantidad': 0, 'total': Decimal('0')})
    por_cajero = defaultdict(lambda: {'cantidad': 0, 'total': Decimal('0')})
    por_metodo = defaultdict(lambda: {'cantidad': 0, 'total': Decimal('0')})
    por_dia = defaultdict(lambda: Decimal('0'))

    for f in filas:
        total_general += f['total']

        por_sede[f['id_sucursal']]['cantidad'] += 1
        por_sede[f['id_sucursal']]['total'] += f['total']

        por_cajero[f['id_cajero']]['cantidad'] += 1
        por_cajero[f['id_cajero']]['total'] += f['total']

        por_metodo[f['metodo_pago']]['cantidad'] += 1
        por_metodo[f['metodo_pago']]['total'] += f['total']

        por_dia[f['fecha'].date()] += f['total']

    return {
        'inicio': inicio.isoformat(),
        'fin': fin.isoformat(),
        'resumen': {
            'total': float(total_general),
            'cantidad_transacciones': len(filas),
        },
        'por_sede': [
            {'id_sucursal': k, 'sede': sedes.get(k, 'Sin sede'),
             'cantidad': v['cantidad'], 'total': float(v['total'])}
            for k, v in sorted(por_sede.items(), key=lambda kv: -kv[1]['total'])
        ],
        'por_cajero': [
            {'id_usuario': k, 'cajero': usuarios.get(k, 'Sin asignar'),
             'cantidad': v['cantidad'], 'total': float(v['total'])}
            for k, v in sorted(por_cajero.items(), key=lambda kv: -kv[1]['total'])
        ],
        'por_metodo': [
            {'metodo_pago': k, 'cantidad': v['cantidad'], 'total': float(v['total'])}
            for k, v in sorted(por_metodo.items())
        ],
        'por_dia': [
            {'fecha': k.isoformat(), 'total': float(v)}
            for k, v in sorted(por_dia.items())
        ],
    }
