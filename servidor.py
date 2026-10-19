"""Servidor de producción (Waitress, funciona en Windows y Linux).

    python servidor.py

run.py sigue sirviendo para desarrollo (recarga automática y depurador),
pero su servidor atiende poco tráfico y su depurador nunca debe quedar
expuesto en internet. Para usuarios reales se usa este archivo.

Variables opcionales del .env:
    PUERTO       (8000)
    HILOS        (32)  peticiones atendidas a la vez
    DB_POOL_SIZE + DB_MAX_OVERFLOW (20 + 20) deben sumar al menos HILOS
"""
import os

from waitress import serve

from app import create_app

app = create_app()

if __name__ == '__main__':
    puerto = int(os.getenv('PUERTO', 8000))
    print(f'Dino Park en http://localhost:{puerto}')
    serve(
        app,
        host='0.0.0.0',
        port=puerto,
        threads=int(os.getenv('HILOS', 32)),
        connection_limit=2000,   # conexiones abiertas a la vez (keep-alive incluido)
        backlog=2048,            # conexiones en espera en el sistema operativo
        channel_timeout=60,      # cierra conexiones inactivas
        ident='DinoPark',
        # Railway (y cualquier proxy inverso) termina el HTTPS y reenvía la
        # petición como HTTP plano agregando cabeceras X-Forwarded-*.
        # Waitress las descarta por defecto (clear_untrusted_proxy_headers);
        # sin esto, url_for(_external=True) arma URLs "http://" en vez de
        # "https://" (ej. el callback de Google OAuth, que Google rechaza).
        trusted_proxy='*',
        trusted_proxy_headers={'x-forwarded-proto', 'x-forwarded-host', 'x-forwarded-for'},
        clear_untrusted_proxy_headers=True,
    )
