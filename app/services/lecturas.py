"""Lecturas manuales de los contadores al abrir y cerrar caja, y su cuadre.

Uso real (lo que marcó el contador físico) = lectura final - lectura inicial.
Se compara con:
  * el CONTADOR DEL SISTEMA: lo que el sistema sumó solo durante el turno, y
  * lo VENDIDO: minutos (dinosaurios) o encendidos (carros y motos) vendidos.
Si alguna diferencia supera la tolerancia, la atracción queda con alerta para el administrador.
"""
from datetime import datetime

from sqlalchemy import func, select

from app.database import db
from app.models.Caja import Caja
from app.models.DetalleVenta import DetalleVenta
from app.models.Flota import Flota
from app.models.LecturaCaja import LecturaCaja, Parametro
from app.models.RegistroUso import RegistroUso
from app.models.Venta import Venta
from app.services import validadores as v
from app.services.errores import ErrorNegocio

TOLERANCIAS_DEFECTO = {'tolerancia_minutos': 5, 'tolerancia_encendidos': 0}
MAX_LECTURA = 10**7


# --------------------------------------------------------------- tolerancias
def obtener_tolerancias():
    valores = dict(TOLERANCIAS_DEFECTO)
    for p in Parametro.query.filter(Parametro.clave.in_(list(valores))):
        valores[p.clave] = int(p.valor)
    return valores


def guardar_tolerancias(minutos, encendidos):
    nuevos = {
        'tolerancia_minutos': v.entero(minutos, 'tolerancia en minutos', 0, 1000),
        'tolerancia_encendidos': v.entero(encendidos, 'tolerancia en encendidos', 0, 1000),
    }
    for clave, valor in nuevos.items():
        p = db.session.get(Parametro, clave)
        if p is None:
            db.session.add(Parametro(clave=clave, valor=str(valor)))
        else:
            p.valor = str(valor)
    db.session.commit()
    return nuevos


def evaluar(tipo, inicial, final, sistema, vendido, tolerancias=None):
    """Calcula uso real, diferencias y alertas de una atracción."""
    tol = tolerancias or obtener_tolerancias()
    limite = tol['tolerancia_minutos'] if tipo == 'minutos' else tol['tolerancia_encendidos']
    unidad = 'min' if tipo == 'minutos' else 'encendidos'
    uso_real = final - inicial
    dif_sistema, dif_vendido = uso_real - sistema, uso_real - vendido
    textos = []
    if abs(dif_sistema) > limite:
        textos.append(f'El contador marcó {uso_real} {unidad} y el sistema registró {sistema} (dif. {dif_sistema:+d}).')
    if abs(dif_vendido) > limite:
        textos.append(f'Se usaron {uso_real} {unidad} pero se vendieron {vendido} (dif. {dif_vendido:+d}).')
    return {'uso_real': uso_real, 'contador_sistema': sistema, 'vendido': vendido,
            'dif_sistema': dif_sistema, 'dif_vendido': dif_vendido,
            'alerta': bool(textos), 'textos': textos}


# ------------------------------------------------------------------ unidades
def unidades_de_la_sede(id_sucursal):
    """(activas, omitidas): solo las disponibles llevan lectura; el resto se omite indicando su estado."""
    todas = Flota.query.filter_by(id_sucursal=id_sucursal).order_by(Flota.tipo, Flota.nombre).all()
    return [f for f in todas if f.estado == 'disponible'], [f for f in todas if f.estado != 'disponible']


def preparar_apertura(id_sucursal):
    activas, omitidas = unidades_de_la_sede(id_sucursal)
    filas = [{'flota': f, 'sugerida': f.lectura_manual, 'primera': f.lectura_manual is None} for f in activas]
    return filas, omitidas


def _leer(form, clave, campo):
    valor = form.get(clave)
    if valor is None or str(valor).strip() == '':
        raise ErrorNegocio(f'Falta {campo}.')
    return v.entero(valor, campo, 0, MAX_LECTURA)


# ------------------------------------------------------------------ apertura
def registrar_apertura(caja, form):
    """Guarda la lectura inicial de cada atracción activa de la sede."""
    activas, _ = unidades_de_la_sede(caja.id_sucursal)
    for f in activas:
        lectura = _leer(form, f'li_{f.id_flota}', f'la lectura inicial de {f.nombre}')
        sugerida, primera = f.lectura_manual, f.lectura_manual is None
        motivo = (form.get(f'mi_{f.id_flota}') or '').strip()
        alerta, texto = False, None
        if not primera and lectura != sugerida:
            if len(motivo) < 3:
                raise ErrorNegocio(
                    f'La lectura inicial de {f.nombre} ({lectura}) es distinta de la del último cierre '
                    f'({sugerida}). Escribe el motivo de la diferencia.')
            alerta = True
            texto = (f'Lectura inicial {lectura} distinta del último cierre {sugerida} '
                     f'(dif. {lectura - sugerida:+d}): posible uso sin registrar.')
        db.session.add(LecturaCaja(
            id_caja=caja.id_caja, id_flota=f.id_flota, tipo_contador=f.tipo_contador,
            lectura_inicial=lectura, sugerida=sugerida, es_primera=primera,
            motivo_apertura=motivo[:200] or None, alerta_apertura=alerta,
            alerta=alerta, alertas=texto,
        ))
        f.lectura_manual = lectura


# -------------------------------------------------------------------- cierre
def validar_cierre(caja, form):
    """Comprueba las lecturas finales ANTES de cerrar. Devuelve {id_lectura: (final, observación)}."""
    datos, faltan = {}, []
    for l in LecturaCaja.query.filter_by(id_caja=caja.id_caja).all():
        if l.flota.estado != 'disponible':
            continue                                   # averiada o inactiva: se omite
        crudo = form.get(f'lf_{l.id_flota}')
        if crudo is None or str(crudo).strip() == '':
            faltan.append(l.flota.nombre)
            continue
        final = v.entero(crudo, f'la lectura final de {l.flota.nombre}', 0, MAX_LECTURA)
        if final < l.lectura_inicial:
            raise ErrorNegocio(
                f'La lectura final de {l.flota.nombre} ({final}) no puede ser menor que la inicial ({l.lectura_inicial}).')
        datos[l.id_lectura] = (final, (form.get(f'of_{l.id_flota}') or '').strip()[:300] or None)
    if faltan:
        raise ErrorNegocio('Falta registrar la lectura final de: ' + ', '.join(faltan) + '.')
    return datos


def _metricas(l, inicio, fin):
    """(contador del sistema, vendido) de una atracción en la ventana del turno."""
    sistema = int(db.session.query(func.coalesce(func.sum(RegistroUso.contador_delta), 0)).filter(
        RegistroUso.id_flota == l.id_flota, RegistroUso.contador_fecha >= inicio,
        RegistroUso.contador_fecha <= fin).scalar())
    medida = (func.coalesce(func.sum(DetalleVenta.minutos), 0) if l.tipo_contador == 'minutos'
              else func.count(DetalleVenta.id_detalle_venta))
    base = (db.session.query(medida).join(Venta, Venta.id_venta == DetalleVenta.id_venta)
            .filter(DetalleVenta.id_flota == l.id_flota, Venta.estado == 'pagada',
                    Venta.id_sucursal == l.caja.id_sucursal))
    presencial = base.filter(Venta.origen == 'presencial', Venta.fecha >= inicio, Venta.fecha <= fin).scalar()
    usados = select(RegistroUso.id_detalle_venta).where(
        RegistroUso.id_flota == l.id_flota, RegistroUso.hora_inicio >= inicio, RegistroUso.hora_inicio <= fin)
    reservas = base.filter(Venta.origen == 'reserva', DetalleVenta.id_detalle_venta.in_(usados)).scalar()
    return sistema, int(presencial or 0) + int(reservas or 0)


def _aplicar(l, final, observacion, sistema, vendido, tolerancias):
    r = evaluar(l.tipo_contador, l.lectura_inicial, final, sistema, vendido, tolerancias)
    l.lectura_final, l.observacion = final, observacion
    l.uso_real, l.contador_sistema, l.vendido = r['uso_real'], r['contador_sistema'], r['vendido']
    l.dif_sistema, l.dif_vendido = r['dif_sistema'], r['dif_vendido']
    textos = ([l.alertas] if l.alerta_apertura and l.alertas else []) + r['textos']
    l.alerta = bool(textos)
    l.alertas = ' | '.join(t for t in textos if t)[:600] or None


def aplicar_cierre(caja, datos):
    """Calcula el cuadre de cada atracción (caja.fecha_cierre ya fijada). Sin commit."""
    tolerancias = obtener_tolerancias()
    for l in LecturaCaja.query.filter_by(id_caja=caja.id_caja).all():
        if l.id_lectura not in datos:
            l.estado_unidad = l.flota.estado           # omitida por avería o inactividad
            continue
        final, observacion = datos[l.id_lectura]
        sistema, vendido = _metricas(l, caja.fecha_apertura, caja.fecha_cierre)
        _aplicar(l, final, observacion, sistema, vendido, tolerancias)
        l.flota.lectura_manual = final                # la próxima apertura la sugerirá


def ajustar(id_lectura, nueva_final, nota, admin):
    """El administrador corrige un cierre ya cerrado; siempre con una justificación."""
    l = db.session.get(LecturaCaja, id_lectura)
    if l is None or l.caja.estado != 'cerrada' or l.lectura_final is None:
        raise ErrorNegocio('Solo se pueden ajustar lecturas de cierres ya cerrados.', 404)
    nota = v.texto(nota, 'justificación', 5, 300)
    final = v.entero(nueva_final, 'lectura final', 0, MAX_LECTURA)
    if final < l.lectura_inicial:
        raise ErrorNegocio('La lectura final no puede ser menor que la inicial.')
    sistema, vendido = l.contador_sistema or 0, l.vendido or 0
    _aplicar(l, final, l.observacion, sistema, vendido, obtener_tolerancias())
    l.nota_admin, l.ajustado_por, l.ajustado_en = nota, admin.id_usuario, datetime.now()
    ultima = (LecturaCaja.query.filter_by(id_flota=l.id_flota).filter(LecturaCaja.lectura_final.isnot(None))
              .order_by(LecturaCaja.id_lectura.desc()).first())
    if ultima and ultima.id_lectura == l.id_lectura:
        l.flota.lectura_manual = final
    db.session.commit()
    return l


# ------------------------------------------------------------------ reportes
def _fila(l):
    c = l.caja
    return {
        'id_lectura': l.id_lectura, 'fecha': c.fecha_cierre or c.fecha_apertura,
        'sede': c.sucursal.nombre, 'cajero': c.usuario.nombre_completo,
        'atraccion': l.flota.nombre, 'tipo_contador': l.tipo_contador,
        'inicial': l.lectura_inicial, 'final': l.lectura_final, 'uso_real': l.uso_real,
        'sistema': l.contador_sistema, 'vendido': l.vendido,
        'dif_sistema': l.dif_sistema, 'dif_vendido': l.dif_vendido,
        'alerta': bool(l.alerta), 'alertas': l.alertas or '',
        'observacion': ' · '.join(x for x in (l.motivo_apertura and f'Apertura: {l.motivo_apertura}',
                                              l.observacion, l.estado_unidad and f'Omitida ({l.estado_unidad})',
                                              l.nota_admin and f'Ajuste admin: {l.nota_admin}') if x),
        'ajustable': l.lectura_final is not None,
    }


def cuadre_atracciones(desde, hasta, id_sucursal=None, solo_alertas=False):
    """Historial de lecturas de cajas cerradas entre dos fechas, más el resumen por atracción."""
    ini = datetime.combine(desde, datetime.min.time())
    fin = datetime.combine(hasta, datetime.max.time())
    consulta = (LecturaCaja.query.join(Caja, Caja.id_caja == LecturaCaja.id_caja)
                .filter(Caja.estado == 'cerrada', Caja.fecha_cierre >= ini, Caja.fecha_cierre <= fin))
    if id_sucursal:
        consulta = consulta.filter(Caja.id_sucursal == id_sucursal)
    if solo_alertas:
        consulta = consulta.filter(LecturaCaja.alerta.is_(True))
    filas = [_fila(l) for l in consulta.order_by(Caja.fecha_cierre.desc(), LecturaCaja.id_lectura).all()]

    resumen = {}
    for f in filas:
        if f['final'] is None:
            continue
        r = resumen.setdefault((f['sede'], f['atraccion']), {
            'sede': f['sede'], 'atraccion': f['atraccion'], 'tipo_contador': f['tipo_contador'],
            'cierres': 0, 'uso_real': 0, 'sistema': 0, 'vendido': 0, 'alertas': 0})
        r['cierres'] += 1
        r['uso_real'] += f['uso_real'] or 0
        r['sistema'] += f['sistema'] or 0
        r['vendido'] += f['vendido'] or 0
        r['alertas'] += 1 if f['alerta'] else 0
    return {'filas': filas, 'resumen': sorted(resumen.values(), key=lambda r: (r['sede'], r['atraccion'])),
            'total_alertas': sum(1 for f in filas if f['alerta']), 'tolerancias': obtener_tolerancias()}


def alertas_del_dia(dia, id_sucursal=None):
    return cuadre_atracciones(dia, dia, id_sucursal, solo_alertas=True)['total_alertas']
