from werkzeug.security import check_password_hash

from app.database import db
from app.models import Cliente, Usuario
from tests.conftest import (ADMIN, CAJERO_REAL, CLAVE, CLIENTE1, iniciar_sesion,
                            usuario)


def test_login_redirige_segun_el_rol(client, como):
    assert '/reportes/dashboard' in iniciar_sesion(client, ADMIN).headers['Location']
    assert '/caja' in como(CAJERO_REAL).get('/iniciar-sesion').headers['Location']
    assert '/disponibilidad' in iniciar_sesion(client, CLIENTE1).headers['Location']


def test_login_por_dni_del_cliente(client):
    r = client.post('/iniciar-sesion', data={'identificador': '70000001', 'contrasena': CLAVE})
    assert r.status_code == 302


def test_login_con_clave_incorrecta(client):
    r = iniciar_sesion(client, ADMIN, 'incorrecta1')
    assert r.status_code == 401
    assert client.get('/reportes/dashboard').status_code == 302     # sigue sin sesión


def test_bloqueo_tras_varios_intentos_fallidos(client):
    for _ in range(5):
        assert iniciar_sesion(client, ADMIN, 'mala1234').status_code == 401
    assert iniciar_sesion(client, ADMIN, CLAVE).status_code == 429   # ya bloqueado


def test_usuario_desactivado_no_entra_ni_conserva_la_sesion(app, como, client):
    admin = como(ADMIN)
    assert admin.get('/reportes/dashboard').status_code == 200
    usuario(ADMIN).estado = False
    db.session.commit()
    assert admin.get('/reportes/dashboard').status_code == 302       # sesión anulada
    assert iniciar_sesion(client, ADMIN).status_code == 401


def test_contrasenas_guardadas_con_hash(app):
    for u in Usuario.query.all():
        assert u.contrasena != CLAVE
        assert check_password_hash(u.contrasena, CLAVE)


def test_registro_crea_siempre_un_cliente(app, client):
    r = client.post('/registro', data={
        'nombres': 'Ana', 'apellidos': 'Rojas', 'dni': '45678912', 'telefono': '987654321',
        'correo': 'ana@correo.pe', 'confirmar_correo': 'ana@correo.pe',
        'contrasena': 'Segura2026', 'confirmar_contrasena': 'Segura2026',
        'terminos': 'on', 'declaracion': 'on', 'rol': 'administrador'})   # intento de escalar rol
    assert r.status_code == 302
    u = usuario('ana@correo.pe')
    assert u.rol_nombre == 'cliente'
    assert Cliente.query.filter_by(dni='45678912').first().id_usuario == u.id_usuario
    assert u.contrasena != 'Segura2026'


def test_registro_valida_entradas(client):
    base = {'nombres': 'Ana', 'apellidos': 'Rojas', 'dni': '45678912', 'telefono': '987654321',
            'correo': 'ana@correo.pe', 'confirmar_correo': 'ana@correo.pe',
            'contrasena': 'Segura2026', 'confirmar_contrasena': 'Segura2026',
            'terminos': 'on', 'declaracion': 'on'}
    for campo, malo in (('dni', '123'), ('telefono', '12'), ('correo', 'sin-arroba'),
                        ('contrasena', 'corta')):
        datos = dict(base, **{campo: malo})
        datos['confirmar_contrasena'] = datos['contrasena']
        datos['confirmar_correo'] = datos['correo']
        assert client.post('/registro', data=datos).status_code == 400, campo


def test_cerrar_sesion_solo_por_post(como):
    c = como(CLIENTE1)
    assert c.get('/cerrar-sesion').status_code == 405
    assert c.post('/cerrar-sesion').status_code == 302
    assert c.get('/disponibilidad').status_code == 302


def test_next_solo_acepta_rutas_internas(client):
    r = client.post('/iniciar-sesion', data={'identificador': CLIENTE1, 'contrasena': CLAVE,
                                             'next': 'https://sitio-malo.com'})
    assert 'sitio-malo' not in r.headers['Location']
