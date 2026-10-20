"""Crea los turnos (horarios reservables) de la flota para los próximos días.

Usa las mismas franjas que app/seed.py: 20 minutos, de 10:00 a 13:00,
capacidad 1, para cada unidad de flota de cada sede.
Se puede ejecutar varias veces: no duplica los turnos que ya existen.

Usa la BD de DATABASE_URL (la del .env, o la que pongas en la terminal).

Uso:
    python crear_turnos.py                     # hoy + 30 días
    python crear_turnos.py --dias 60           # hoy + 60 días
    python crear_turnos.py --desde 2026-11-01  # desde esa fecha
    python crear_turnos.py --simular           # solo muestra cuántos crearía
"""
import argparse
import sys
from datetime import date, datetime, time, timedelta

from app import create_app
from app.database import db
from app.models.Flota import Flota
from app.models.Turno import Turno

HORARIOS = [
    (time(10, 0), time(10, 20)),
    (time(10, 30), time(10, 50)),
    (time(11, 0), time(11, 20)),
    (time(11, 30), time(11, 50)),
    (time(12, 0), time(12, 20)),
    (time(12, 30), time(12, 50)),
]


def leer_argumentos():
    parser = argparse.ArgumentParser(description='Crea los turnos de la flota.')
    parser.add_argument('--dias', type=int, default=30,
                        help='cuántos días crear (por defecto 30)')
    parser.add_argument('--desde', type=date.fromisoformat, default=date.today(),
                        help='primer día, AAAA-MM-DD (por defecto hoy)')
    parser.add_argument('--simular', action='store_true',
                        help='no guarda nada, solo muestra cuántos crearía')
    return parser.parse_args()


def main():
    args = leer_argumentos()
    if args.dias < 1:
        print('--dias debe ser al menos 1.')
        sys.exit(1)

    app = create_app({'SEMBRAR_DATOS': False})

    with app.app_context():
        print(f'BD: {db.engine.url.render_as_string(hide_password=True)}')

        unidades = Flota.query.order_by(Flota.id_flota).all()
        if not unidades:
            print('FALLO: no hay unidades de flota en la BD.')
            sys.exit(1)

        dias = [args.desde + timedelta(days=i) for i in range(args.dias)]
        fin = datetime.combine(dias[-1] + timedelta(days=1), time())

        # Turnos que ya existen en el rango, para no duplicarlos
        existentes = {
            (t.id_flota, t.horario_inicio)
            for t in Turno.query.filter(
                Turno.horario_inicio >= datetime.combine(dias[0], time()),
                Turno.horario_inicio < fin,
            )
        }

        nuevos = 0
        for unidad in unidades:
            for dia in dias:
                for hora_inicio, hora_fin in HORARIOS:
                    inicio = datetime.combine(dia, hora_inicio)
                    if (unidad.id_flota, inicio) in existentes:
                        continue
                    db.session.add(Turno(
                        fecha=datetime.combine(dia, time()),
                        horario_inicio=inicio,
                        horario_fin=datetime.combine(dia, hora_fin),
                        estado='disponible',
                        capacidad=1,
                        id_flota=unidad.id_flota,
                    ))
                    nuevos += 1

        print(f'{len(unidades)} unidades de flota, del {dias[0]} al {dias[-1]}.')
        print(f'Ya existían {len(existentes)} turnos; nuevos: {nuevos}.')

        if args.simular:
            db.session.rollback()
            print('Simulación: no se guardó nada.')
            return

        db.session.commit()
        print('Turnos guardados.')


if __name__ == '__main__':
    main()
