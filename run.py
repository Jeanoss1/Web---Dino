import os

from app import create_app
from app.scheduler import iniciar_planificador

app = create_app()

if __name__ == '__main__':
    # Con el recargador de Flask (debug) solo el proceso hijo inicia el planificador,
    # para no finalizar alquileres desde dos procesos.
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        iniciar_planificador(app)
    app.run(debug=app.config['DEBUG'])
