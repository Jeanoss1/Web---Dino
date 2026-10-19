"""Cuadre diario: dinero (reusa servicios_reportes, no se duplica) + minutos
vendidos vs minutos realmente usados, tanto en entradas por tiempo (Hoyos
Rubio, vía `id_paquete`) como en alquiler de flota por turno fijo (Real
Plaza/Mega Plaza, vía `id_flota`). Si no se cierra a tiempo (ni "marcar
salida"/"cobrar adicional" en Hoyos Rubio, ni "finalizar alquiler" en
flota), aquí queda como alerta."""

from collections import defaultdict
from datetime import datetime, timedelta

from app.database import db
from app.models.Caja import Caja
from app.models.DetalleReservaEntrada import DetalleReservaEntrada
from app.models.DetalleVenta import DetalleVenta
from app.models.LecturaFlota import LecturaFlota
from app.models.ReservaEntrada import ReservaEntrada
from app.models.usuario import Usuario
from app.models.Venta import Venta
from app.servicios_reportes import generar_reporte

TOLERANCIA_MINUTOS = 5


def _minutos(inicio, fin):
    return (fin - inicio).total_seconds() / 60


def _fila_cajero():
    return {'minutos_vendidos': 0, 'minutos_usados': 0, 'en_curso': 0}


def cuadre_minutos(fecha, id_sucursal=None):
    desde_dt = datetime.combine(fecha, datetime.min.time())
    hasta_dt = desde_dt + timedelta(days=1)

    filas = defaultdict(_fila_cajero)

    consulta_venta = (
        DetalleVenta.query
        .join(Venta)
        .filter(
            db.or_(DetalleVenta.id_paquete.isnot(None), DetalleVenta.id_flota.isnot(None)),
            DetalleVenta.hora_inicio >= desde_dt,
            DetalleVenta.hora_inicio < hasta_dt,
            Venta.estado == 'pagada',
        )
    )
    if id_sucursal:
        consulta_venta = consulta_venta.filter(Venta.id_sucursal == id_sucursal)

    for d in consulta_venta.all():
        fila = filas[d.venta.id_usuario]
        duracion = d.paquete.duracion_minutos if d.id_paquete else d.flota.duracion_alquiler_minutos
        fila['minutos_vendidos'] += (duracion or 0) * d.cantidad
        if d.hora_fin:
            fila['minutos_usados'] += _minutos(d.hora_inicio, d.hora_fin)
        else:
            fila['en_curso'] += 1

    consulta_entrada = (
        DetalleReservaEntrada.query
        .join(ReservaEntrada)
        .filter(
            DetalleReservaEntrada.hora_inicio >= desde_dt,
            DetalleReservaEntrada.hora_inicio < hasta_dt,
            ReservaEntrada.estado == 'confirmada',
        )
    )
    if id_sucursal:
        consulta_entrada = consulta_entrada.filter(ReservaEntrada.id_sucursal == id_sucursal)

    for d in consulta_entrada.all():
        comprobante = next(
            (c for c in reversed(d.reserva_entrada.comprobantes) if c.estado == 'aceptado'),
            None,
        )
        fila = filas[comprobante.id_validador if comprobante else None]
        fila['minutos_vendidos'] += (d.paquete.duracion_minutos or 0) * d.cantidad
        if d.hora_fin:
            fila['minutos_usados'] += _minutos(d.hora_inicio, d.hora_fin)
        else:
            fila['en_curso'] += 1

    usuarios = {u.id_usuario: f'{u.nombre} {u.apellido}' for u in Usuario.query.all()}

    resultado = []
    for id_usuario, fila in filas.items():
        diferencia = fila['minutos_vendidos'] - fila['minutos_usados']
        alerta = abs(diferencia) > TOLERANCIA_MINUTOS or fila['en_curso'] > 0
        resultado.append({
            'id_usuario': id_usuario,
            'cajero': usuarios.get(id_usuario, 'Sin asignar'),
            'minutos_vendidos': round(fila['minutos_vendidos'], 1),
            'minutos_usados': round(fila['minutos_usados'], 1),
            'en_curso': fila['en_curso'],
            'diferencia': round(diferencia, 1),
            'alerta': alerta,
        })

    resultado.sort(key=lambda f: (not f['alerta'], f['cajero']))
    return resultado


def lecturas_del_dia(fecha, id_sucursal=None):
    """Lecturas manuales (apertura/cierre) de las cajas abiertas ese día,
    con la diferencia física vs. contador del sistema ya calculada."""
    desde_dt = datetime.combine(fecha, datetime.min.time())
    hasta_dt = desde_dt + timedelta(days=1)

    consulta = (
        LecturaFlota.query
        .join(Caja)
        .filter(Caja.fecha_apertura >= desde_dt, Caja.fecha_apertura < hasta_dt)
    )
    if id_sucursal:
        consulta = consulta.filter(Caja.id_sucursal == id_sucursal)

    usuarios = {u.id_usuario: f'{u.nombre} {u.apellido}' for u in Usuario.query.all()}

    resultado = []
    for l in consulta.order_by(LecturaFlota.id_caja, LecturaFlota.id_flota, LecturaFlota.momento).all():
        resultado.append({
            'id_caja': l.id_caja,
            'cajero': usuarios.get(l.caja.id_usuario, 'Sin asignar'),
            'unidad': l.flota.nombre,
            'momento': l.momento,
            'lectura_manual': l.lectura_manual,
            'contador_sistema': l.contador_sistema,
            'diferencia': l.diferencia,
            'alerta': l.diferencia != 0,
        })
    return resultado


def cuadre_diario(fecha, id_sucursal=None):
    dinero = generar_reporte(id_sucursal=id_sucursal, rango='diario', referencia=fecha)
    minutos = cuadre_minutos(fecha, id_sucursal)
    lecturas = lecturas_del_dia(fecha, id_sucursal)

    return {
        'fecha': fecha.isoformat(),
        'dinero': dinero,
        'minutos': minutos,
        'lecturas': lecturas,
        'total_alertas': sum(1 for m in minutos if m['alerta']) + sum(1 for l in lecturas if l['alerta']),
    }
