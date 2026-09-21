"""Cierre diario: minutos vendidos vs. usados y dinero vendido vs. dinero en caja."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import current_app
from sqlalchemy import func

from app.database import db
from app.models.Caja import Caja
from app.models.DetalleVenta import DetalleVenta
from app.models.RegistroUso import RegistroUso
from app.models.Venta import Venta
from app.services import cajas, turnos

CERO = Decimal('0')


def rango_dia(dia):
    inicio = datetime.combine(dia, datetime.min.time())
    return inicio, inicio + timedelta(days=1)


def _fila_cajero(cajero, dia, tolerancia):
    inicio, fin = rango_dia(dia)
    filtro_venta = (Venta.id_usuario == cajero.id_usuario, Venta.estado == 'pagada',
                    Venta.fecha >= inicio, Venta.fecha < fin)
    ventas = Venta.query.filter(*filtro_venta).all()
    efectivo = sum((x.total for x in ventas if x.tipo_pago == 'efectivo'), CERO)
    yape = sum((x.total for x in ventas if x.tipo_pago == 'yape'), CERO)
    minutos_vendidos = int(db.session.query(func.coalesce(func.sum(DetalleVenta.minutos), 0))
                           .join(Venta, Venta.id_venta == DetalleVenta.id_venta)
                           .filter(*filtro_venta).scalar())
    usos = RegistroUso.query.filter(
        RegistroUso.id_usuario == cajero.id_usuario,
        RegistroUso.hora_inicio >= inicio, RegistroUso.hora_inicio < fin).all()
    minutos_usados = sum(u.minutos_usados or 0 for u in usos if u.estado == 'finalizado')
    en_curso = sum(1 for u in usos if u.estado == 'en_curso')

    lista_cajas = Caja.query.filter(
        Caja.id_usuario == cajero.id_usuario, Caja.fecha_apertura >= inicio,
        Caja.fecha_apertura < fin).order_by(Caja.id_caja).all()
    abiertas = [c for c in lista_cajas if c.estado == 'abierta']
    cerradas = [c for c in lista_cajas if c.estado == 'cerrada']
    esperado = sum((c.efectivo_esperado or CERO for c in cerradas), CERO)
    contado = sum((c.monto_final or CERO for c in cerradas), CERO)
    esperado += sum((cajas.resumen(c)['efectivo_esperado'] for c in abiertas), CERO)
    diferencia_efectivo = (contado - sum((c.efectivo_esperado or CERO for c in cerradas), CERO)
                           if cerradas else None)

    estado_caja = 'sin apertura'
    if abiertas:
        estado_caja = 'abierta'
    elif cerradas:
        estado_caja = 'cerrada'

    diferencia_minutos = minutos_vendidos - minutos_usados
    alertas = []
    if abs(diferencia_minutos) > tolerancia:
        if diferencia_minutos > 0:
            alertas.append(f'Se vendieron {diferencia_minutos} min más de los que se usaron.')
        else:
            alertas.append(f'Se usaron {-diferencia_minutos} min más de los vendidos.')
    if diferencia_efectivo is not None and abs(diferencia_efectivo) >= Decimal('0.01'):
        signo = 'Sobran' if diferencia_efectivo > 0 else 'Faltan'
        alertas.append(f'{signo} S/ {abs(diferencia_efectivo):.2f} en caja.')
    if en_curso:
        alertas.append(f'{en_curso} vehículo(s) siguen en uso.')
    if abiertas and dia < date.today():
        alertas.append('La caja no se cerró.')

    return {
        'id_cajero': cajero.id_cajero, 'cajero': cajero.nombre, 'sede': cajero.sucursal.nombre,
        'id_sucursal': cajero.id_sucursal, 'tipo_turno': cajero.tipo_turno,
        'ventas': len(ventas), 'vendido_efectivo': efectivo, 'vendido_yape': yape,
        'vendido_total': efectivo + yape,
        'minutos_vendidos': minutos_vendidos, 'minutos_usados': minutos_usados,
        'diferencia_minutos': diferencia_minutos,
        'estado_caja': estado_caja, 'efectivo_esperado': esperado,
        'efectivo_contado': contado if cerradas else None,
        'diferencia_efectivo': diferencia_efectivo,
        'alertas': alertas,
    }


def cuadre_diario(dia, id_sucursal=None):
    from app.services import uso
    uso.finalizar_vencidos()
    tolerancia = current_app.config['TOLERANCIA_MINUTOS']
    filas = [_fila_cajero(c, dia, tolerancia) for c in turnos.cajeros_activos(id_sucursal)]
    sedes = {}
    for f in filas:
        s = sedes.setdefault(f['id_sucursal'], {
            'sede': f['sede'], 'ventas': 0, 'vendido_total': CERO, 'vendido_efectivo': CERO,
            'vendido_yape': CERO, 'minutos_vendidos': 0, 'minutos_usados': 0, 'alertas': 0})
        s['ventas'] += f['ventas']
        s['vendido_total'] += f['vendido_total']
        s['vendido_efectivo'] += f['vendido_efectivo']
        s['vendido_yape'] += f['vendido_yape']
        s['minutos_vendidos'] += f['minutos_vendidos']
        s['minutos_usados'] += f['minutos_usados']
        s['alertas'] += len(f['alertas'])
    for s in sedes.values():
        s['diferencia_minutos'] = s['minutos_vendidos'] - s['minutos_usados']
    return {
        'fecha': dia, 'filas': filas, 'sedes': list(sedes.values()),
        'total_alertas': sum(len(f['alertas']) for f in filas),
    }
