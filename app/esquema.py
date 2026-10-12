"""Pone al día una BD que ya existía.

`db.create_all()` solo crea tablas nuevas: no agrega columnas ni índices a
las tablas que ya están creadas. Esto completa lo que falte comparando los
modelos con la BD real. Solo agrega (nunca borra ni cambia nada) y se puede
ejecutar todas las veces que se quiera.
"""
from sqlalchemy import inspect, text

from app.database import db


def actualizar_esquema():
    inspector = inspect(db.engine)
    tablas = set(inspector.get_table_names())

    with db.engine.begin() as con:
        for tabla in db.metadata.sorted_tables:
            if tabla.name not in tablas:
                continue   # la acaba de crear create_all() con todo

            existentes = {c['name'] for c in inspector.get_columns(tabla.name)}
            for columna in tabla.columns:
                if columna.name in existentes or not columna.nullable:
                    continue
                tipo = columna.type.compile(dialect=con.dialect)
                con.execute(text(
                    f'ALTER TABLE "{tabla.name}" '
                    f'ADD COLUMN IF NOT EXISTS "{columna.name}" {tipo}'
                ))
                print(f'[esquema] Columna agregada: {tabla.name}.{columna.name}')

            for indice in tabla.indexes:
                indice.create(con, checkfirst=True)
