from datetime import datetime
from decimal import Decimal

from sqlalchemy import func

from app.database import db
from app.models.Caja import Caja
from app.models.DetalleVenta import DetalleVenta
from app.models.MovimientoCaja import MovimientoCaja
from app.models.RegistroUso import RegistroUso
from app.models.Venta import Venta
from app.services import validadores as v
from app.services.errores import ErrorNegocio

CERO = Decimal('0')


def caja_abierta(id_usuario):
    return Caja.query.filter_by(id_usuario=id_usuario, estado='abierta').first()


def abrir(usuario, cajero, monto_inicial, form=None):
    if cajero is None or cajero.estado != 'activo':
        raise ErrorNegocio('Solo un cajero activo puede abrir una caja.', 403)
    if caja_abierta(usuario.id_usuario):
        raise ErrorNegocio('Ya tienes una caja abierta.')
    monto = v.dinero(monto_inicial or '0', 'monto inicial')
    caja = Caja(
        fecha_apertura=datetime.now(), monto_inicial=monto, estado='abierta',
        id_usuario=usuario.id_usuario, id_sucursal=cajero.id_sucursal,
    )
    db.session.add(caja)
    db.session.flush()
    from app.services import lecturas
    lecturas.registrar_apertura(caja, form or {})      # lectura inicial de cada atracción activa
    db.session.commit()
    return caja


def registrar_movimiento(caja, tipo, monto, descripcion):
    if caja is None or caja.estado != 'abierta':
        raise ErrorNegocio('Primero debes abrir la caja.')
    if tipo not in ('ingreso', 'egreso'):
        raise ErrorNegocio("El tipo debe ser 'ingreso' o 'egreso'.")
    monto = v.dinero(monto, 'monto', permitir_cero=False)
    descripcion = v.texto(descripcion, 'descripción', 3, 200)
    db.session.add(MovimientoCaja(
        tipo=tipo, monto=monto, descripcion=descripcion, origen='manual',
        id_caja=caja.id_caja,
    ))
    db.session.commit()


def _suma_movimientos(caja, tipo, origen=None):
    consulta = db.session.query(func.coalesce(func.sum(MovimientoCaja.monto), 0)).filter(
        MovimientoCaja.id_caja == caja.id_caja, MovimientoCaja.tipo == tipo
    )
    if origen:
        consulta = consulta.filter(MovimientoCaja.origen == origen)
    return Decimal(str(consulta.scalar()))


def resumen(caja, finalizar=True):
    """Cuadre de una caja: dinero (efectivo + Yape) y minutos (vendidos vs. usados)."""
    if finalizar:
        from app.services import uso
        uso.finalizar_vencidos()
    fin = caja.fecha_cierre or datetime.now()
    ventas = Venta.query.filter(
        Venta.id_usuario == caja.id_usuario, Venta.estado == 'pagada',
        Venta.fecha >= caja.fecha_apertura, Venta.fecha <= fin,
    )
    total_efectivo = sum((x.total for x in ventas.filter(Venta.tipo_pago == 'efectivo')), CERO)
    total_yape = sum((x.total for x in ventas.filter(Venta.tipo_pago == 'yape')), CERO)
    minutos_vendidos = db.session.query(func.coalesce(func.sum(DetalleVenta.minutos), 0)).join(
        Venta, Venta.id_venta == DetalleVenta.id_venta
    ).filter(
        Venta.id_usuario == caja.id_usuario, Venta.estado == 'pagada',
        Venta.fecha >= caja.fecha_apertura, Venta.fecha <= fin,
    ).scalar()
    minutos_usados = db.session.query(func.coalesce(func.sum(RegistroUso.minutos_usados), 0)).filter(
        RegistroUso.id_usuario == caja.id_usuario, RegistroUso.estado == 'finalizado',
        RegistroUso.hora_inicio >= caja.fecha_apertura, RegistroUso.hora_inicio <= fin,
    ).scalar()

    ingresos_venta = _suma_movimientos(caja, 'ingreso', 'venta')
    ingresos_manual = _suma_movimientos(caja, 'ingreso', 'manual')
    egresos = _suma_movimientos(caja, 'egreso')
    inicial = caja.monto_inicial or CERO
    esperado = inicial + ingresos_venta + ingresos_manual - egresos
    return {
        'monto_inicial': inicial,
        'ingresos_venta': ingresos_venta,
        'ingresos_manual': ingresos_manual,
        'egresos': egresos,
        'efectivo_esperado': esperado,
        'total_efectivo': total_efectivo,
        'total_yape': total_yape,
        'total_vendido': total_efectivo + total_yape,
        'minutos_vendidos': int(minutos_vendidos),
        'minutos_usados': int(minutos_usados),
        'diferencia_minutos': int(minutos_vendidos) - int(minutos_usados),
    }


def cerrar(caja, monto_contado, observacion='', form=None):
    if caja is None or caja.estado != 'abierta':
        raise ErrorNegocio('No tienes una caja abierta.')
    from app.services import uso
    uso.finalizar_vencidos()
    en_curso = RegistroUso.query.filter_by(id_usuario=caja.id_usuario, estado='en_curso').count()
    if en_curso:
        raise ErrorNegocio(
            f'Hay {en_curso} vehículo(s) en uso. Espera a que termine su tiempo o finalízalo antes.'
        )
    from app.services import lecturas
    contado = v.dinero(monto_contado, 'efectivo contado')
    datos_lecturas = lecturas.validar_cierre(caja, form or {})   # falla antes de cerrar nada
    caja.fecha_cierre = datetime.now()          # antes de resumir, fija la ventana
    r = resumen(caja, finalizar=False)
    caja.estado = 'cerrada'
    caja.monto_final = contado
    caja.efectivo_esperado = r['efectivo_esperado']
    caja.diferencia = contado - r['efectivo_esperado']
    caja.total_efectivo = r['total_efectivo']
    caja.total_yape = r['total_yape']
    caja.minutos_vendidos = r['minutos_vendidos']
    caja.minutos_usados = r['minutos_usados']
    caja.observacion = (observacion or '').strip()[:300] or None
    db.session.flush()
    lecturas.aplicar_cierre(caja, datos_lecturas)
    db.session.commit()
    return caja
