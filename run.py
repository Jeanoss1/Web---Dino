from app import create_app
from app.database import db

# --- IMPORTA TODOS TUS MODELOS AQUÍ ---
# Asegúrate de que las mayúsculas coincidan con los nombres de tus archivos
from app.models.Caja import Caja
from app.models.Cliente import Cliente
from app.models.DetalleReserva import DetalleReserva
from app.models.DetalleVenta import DetalleVenta
from app.models.Flota import Flota
from app.models.Mantenimiento import Mantenimiento
from app.models.MovimientoCaja import MovimientoCaja
from app.models.Pago import Pago
from app.models.Repuesto import Repuesto
from app.models.Reserva import Reserva
from app.models.Rol import Rol
from app.models.Sucursal import Sucursal
from app.models.Ticket import Ticket
from app.models.Turno import Turno
from app.models.usuario import Usuario  # Este está en minúscula en tu carpeta
from app.models.Venta import Venta      # Asumiendo que ya le quitaste la doble "t"
# --------------------------------------

app = create_app()

# Este bloque crea las tablas que acabamos de importar
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)