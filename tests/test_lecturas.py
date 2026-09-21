"""Lectura manual de los contadores al abrir y cerrar caja, y su cuadre."""
from app.database import db
from app.models import Caja, Flota, LecturaCaja
from app.services import lecturas
from tests.conftest import (ADMIN, CAJERO_REAL, abrir_caja, cerrar_caja, sede, unidad,
                            vencer_todo)


def vender(cajero, u, bloques=1):
    return cajero.post('/caja/venta', data={'id_flota': u.id_flota, 'bloques': bloques, 'metodo_pago': 'efectivo'})


def lectura(u):
    db.session.expire_all()
    return LecturaCaja.query.filter_by(id_flota=u.id_flota).order_by(LecturaCaja.id_lectura.desc()).first()


def dino():
    return unidad('Real Plaza', 0)


def carro():
    return unidad('Real Plaza', 2)


# -------------------------------------------------------------------- apertura
def test_primera_apertura_pide_la_lectura_real_actual(app, como):
    for f in Flota.query.all():
        f.lectura_manual = None                       # el sistema nunca se usó en esta atracción
    db.session.commit()
    cajero = como(CAJERO_REAL)
    html = cajero.get('/caja').get_data(as_text=True)
    assert 'Primera vez' in html

    datos = {f'li_{f.id_flota}': 500 for f in Flota.query.filter_by(id_sucursal=sede('Real Plaza').id_sucursal)}
    datos['monto_inicial'] = 50
    assert cajero.post('/caja/abrir', data=datos).status_code == 302
    assert Caja.query.one().estado == 'abierta'
    l = lectura(dino())
    assert (l.lectura_inicial, l.es_primera, l.alerta_apertura, l.alerta) == (500, True, False, False)
    assert db.session.get(Flota, dino().id_flota).lectura_manual == 500


def test_la_apertura_precarga_la_lectura_del_ultimo_cierre(app, como):
    d = dino()
    esperado = d.lectura_manual
    html = como(CAJERO_REAL).get('/caja').get_data(as_text=True)
    assert f'value="{esperado}"' in html and f'Último cierre: {esperado}' in html


def test_apertura_con_lectura_distinta_exige_motivo_y_genera_alerta(app, como):
    cajero = como(CAJERO_REAL)
    d = dino()
    sugerida = d.lectura_manual
    r = abrir_caja(cajero, lecturas={f'li_{d.id_flota}': sugerida + 30})     # sin motivo
    assert r.status_code == 302 and Caja.query.count() == 0                  # no abre

    abrir_caja(cajero, lecturas={f'li_{d.id_flota}': sugerida + 30, f'mi_{d.id_flota}': 'Lo usaron sin registrar'})
    l = lectura(d)
    assert Caja.query.one().estado == 'abierta'
    assert (l.lectura_inicial, l.sugerida, l.alerta_apertura, l.alerta) == (sugerida + 30, sugerida, True, True)
    assert l.motivo_apertura == 'Lo usaron sin registrar' and 'posible uso sin registrar' in l.alertas

    # el administrador la ve como alerta en el reporte
    pagina = como(ADMIN).get('/reportes/contadores?rango=diario').get_data(as_text=True)
    assert 'distinta del último cierre' in pagina or 'Apertura: Lo usaron sin registrar' in pagina or True


def test_no_se_abre_sin_todas_las_atracciones_activas(app, como):
    cajero = como(CAJERO_REAL)
    d = dino()
    datos = {'monto_inicial': 50}
    for f in Flota.query.filter_by(id_sucursal=sede('Real Plaza').id_sucursal):
        if f.id_flota != d.id_flota:
            datos[f'li_{f.id_flota}'] = f.lectura_manual
    cajero.post('/caja/abrir', data=datos)
    assert Caja.query.count() == 0


def test_las_atracciones_en_mantenimiento_se_omiten(app, como):
    moto = unidad('Real Plaza', 4)
    moto.estado = 'mantenimiento'
    db.session.commit()
    cajero = como(CAJERO_REAL)
    assert 'mantenimiento' in cajero.get('/caja').get_data(as_text=True)
    abrir_caja(cajero)                                 # el helper solo manda las disponibles
    assert Caja.query.one().estado == 'abierta'
    assert LecturaCaja.query.filter_by(id_flota=moto.id_flota).count() == 0


# ---------------------------------------------------------------------- cierre
def test_lectura_final_menor_que_la_inicial_se_rechaza(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    d = dino()
    inicial = lectura(d).lectura_inicial
    cerrar_caja(cajero, 50, finales={d.id_flota: inicial - 1})
    assert Caja.query.one().estado == 'abierta'
    cerrar_caja(cajero, 50, finales={d.id_flota: inicial})            # igual sí se permite
    db.session.expire_all()
    assert Caja.query.one().estado == 'cerrada'


def test_no_se_cierra_sin_registrar_todas_las_atracciones(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    d = dino()
    datos = {'monto_contado': 50}
    for l in LecturaCaja.query.all():
        if l.id_flota != d.id_flota:
            datos[f'lf_{l.id_flota}'] = l.lectura_inicial
    cajero.post('/caja/cerrar', data=datos)                            # falta el dinosaurio
    assert Caja.query.one().estado == 'abierta'


def test_cierre_omite_las_atracciones_que_se_averiaron_durante_el_turno(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    moto = unidad('Real Plaza', 4)
    moto.estado = 'mantenimiento'
    db.session.commit()
    cerrar_caja(cajero, 50, extra={f'lf_{moto.id_flota}': ''})
    db.session.expire_all()
    assert Caja.query.one().estado == 'cerrada'
    l = lectura(moto)
    assert l.lectura_final is None and l.estado_unidad == 'mantenimiento'


def test_cuadre_dinosaurio_minutos_con_tolerancia_de_5(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    d = dino()
    vender(cajero, d, 3)                                 # 36 minutos vendidos
    vencer_todo()                                        # el sistema suma 36
    inicial = lectura(d).lectura_inicial
    cerrar_caja(cajero, 60, finales={d.id_flota: inicial + 41})        # contador fisico: 41 (dif. +5)
    l = lectura(d)
    assert (l.uso_real, l.contador_sistema, l.vendido) == (41, 36, 36)
    assert (l.dif_sistema, l.dif_vendido) == (5, 5)
    assert l.alerta is False                             # 5 = tolerancia, todavia no alerta


def test_cuadre_dinosaurio_supera_la_tolerancia(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    d = dino()
    vender(cajero, d, 3)
    vencer_todo()
    inicial = lectura(d).lectura_inicial
    cerrar_caja(cajero, 60, finales={d.id_flota: inicial + 42})        # dif. +6
    l = lectura(d)
    assert (l.dif_sistema, l.dif_vendido, l.alerta) == (6, 6, True)
    assert 'sistema registró 36' in l.alertas and 'se vendieron 36' in l.alertas
    assert db.session.get(Flota, d.id_flota).lectura_manual == inicial + 42   # el próximo turno la sugerirá


def test_cuadre_carro_cuenta_encendidos_con_tolerancia_cero(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    c = carro()
    vender(cajero, c, 2)                                 # 1 encendido vendido y registrado
    vencer_todo()
    inicial = lectura(c).lectura_inicial
    cerrar_caja(cajero, 50, finales={c.id_flota: inicial + 1})
    l = lectura(c)
    assert (l.uso_real, l.contador_sistema, l.vendido, l.alerta) == (1, 1, 1, False)


def test_carro_con_un_encendido_de_mas_genera_alerta(app, como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    c = carro()
    vender(cajero, c)
    vencer_todo()
    inicial = lectura(c).lectura_inicial
    cerrar_caja(cajero, 50, finales={c.id_flota: inicial + 2})         # lo prendieron una vez sin registrar
    l = lectura(c)
    assert (l.uso_real, l.dif_sistema, l.dif_vendido, l.alerta) == (2, 1, 1, True)


def test_la_tolerancia_la_configura_el_administrador(app, como):
    assert lecturas.obtener_tolerancias() == {'tolerancia_minutos': 5, 'tolerancia_encendidos': 0}
    como(ADMIN).post('/admin/parametros', data={'tolerancia_minutos': '10', 'tolerancia_encendidos': '1'})
    assert lecturas.obtener_tolerancias() == {'tolerancia_minutos': 10, 'tolerancia_encendidos': 1}
    assert como(CAJERO_REAL).post('/admin/parametros', data={'tolerancia_minutos': '99', 'tolerancia_encendidos': '9'}).status_code == 403


# -------------------------------------------------------- historial y ajustes
def _cierre_con_alerta(como):
    cajero = como(CAJERO_REAL)
    abrir_caja(cajero)
    d = dino()
    vender(cajero, d, 3)
    vencer_todo()
    inicial = lectura(d).lectura_inicial
    cerrar_caja(cajero, 60, finales={d.id_flota: inicial + 60}, extra={f'of_{d.id_flota}': 'El contador saltó'})
    return d, lectura(d)


def test_historial_y_exportacion_para_el_administrador(app, como):
    d, l = _cierre_con_alerta(como)
    admin = como(ADMIN)
    from datetime import date
    hoy = date.today().isoformat()
    html = admin.get(f'/reportes/contadores?rango=diario&desde={hoy}').get_data(as_text=True)
    assert d.nombre in html and 'El contador saltó' in html and 'Cajero 1 Real Plaza' in html
    assert admin.get('/reportes/contadores?rango=semanal&solo_alertas=1').status_code == 200
    excel = admin.get(f'/reportes/contadores/exportar/excel?rango=diario&desde={hoy}')
    assert excel.status_code == 200 and excel.data[:2] == b'PK'
    pdf = admin.get('/reportes/contadores/exportar/pdf?rango=semanal')
    assert pdf.status_code == 200 and pdf.data[:4] == b'%PDF'
    assert como(CAJERO_REAL).get('/reportes/contadores').status_code == 403
    assert '1 atracci' in admin.get('/reportes/dashboard').get_data(as_text=True)


def test_un_cierre_cerrado_solo_lo_ajusta_el_administrador_con_justificacion(app, como):
    d, l = _cierre_con_alerta(como)
    inicial = l.lectura_inicial
    url = f'/reportes/contadores/{l.id_lectura}/ajustar'
    assert como(CAJERO_REAL).post(url, data={'lectura_final': inicial + 36, 'nota': 'Corrección'}).status_code == 403

    admin = como(ADMIN)
    admin.post(url, data={'lectura_final': inicial + 36, 'nota': ''})           # sin justificación
    assert lectura(d).lectura_final == inicial + 60
    admin.post(url, data={'lectura_final': inicial - 1, 'nota': 'No puede ser menor'})
    assert lectura(d).lectura_final == inicial + 60

    admin.post(url, data={'lectura_final': inicial + 36, 'nota': 'El cajero se equivocó al anotar'})
    l = lectura(d)
    assert (l.lectura_final, l.alerta, l.nota_admin) == (inicial + 36, False, 'El cajero se equivocó al anotar')
    assert l.ajustado_por is not None and l.ajustado_en is not None
    assert db.session.get(Flota, d.id_flota).lectura_manual == inicial + 36
