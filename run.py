from app import create_app
from app.database import db

# Carga todos los modelos mediante app/models/__init__.py
from app import models


app = create_app()

# Este bloque crea las tablas que acabamos de importar
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)