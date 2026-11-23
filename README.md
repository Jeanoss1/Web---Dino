# Dino Park · Sistema web de reservas, caja y flota

Sistema web de **Dino Park Perú S.A.C.**, empresa que alquila dinosaurios mecánicos, carros y motos infantiles en centros comerciales de Cajamarca. Reemplaza la aplicación de terceros que usaba la empresa y centraliza la reserva de turnos en línea, el pago con Yape, la venta en taquilla, la caja, el mantenimiento de la flota y los reportes administrativos de sus tres sedes (Real Plaza, Mega Plaza y Hoyos Rubio).

Proyecto del curso **Calidad y Pruebas de Software** (Universidad Privada del Norte).

- Sistema desplegado: https://dino-park-web.onrender.com/
- Tablero del proyecto (historias de usuario): https://github.com/users/Jeanoss1/projects/6

## Funcionalidades por rol

| Rol | Qué puede hacer |
|---|---|
| **Cliente** | Registrarse (o entrar con Google), consultar sedes, flota y turnos disponibles, reservar una o varias atracciones, subir la captura de pago de Yape, ver y cancelar sus reservas, y descargar su ticket de acceso cuando el pago es aceptado. |
| **Cajero** | Abrir y cerrar caja con lecturas de contador, registrar movimientos, vender en taquilla (alquiler de flota o entradas por tiempo), validar los comprobantes de las reservas en línea y validar o usar los tickets de acceso. El menú depende de su sede: flota por turnos (Real Plaza y Mega Plaza) o entradas por tiempo (Hoyos Rubio). |
| **Administrador** | Gestionar sedes, zonas, paquetes, flota, usuarios y horarios de cajeros; registrar mantenimientos y ver alertas preventivas por límite de uso; consultar reportes de ventas (diario, semanal, mensual o personalizado, por sede, cajero y método de pago), exportarlos a PDF y revisar el cuadre diario. |

## Historias de usuario

| Código | Historia | Detalle |
|---|---|---|
| HU01 | Inicio de sesión y control de acceso | Correo o DNI, "Recordarme", Google OAuth, permisos por rol |
| HU02 | Consulta de disponibilidad y reserva de turnos | Turnos de 30 minutos, sin sobreventa ni unidades en mantenimiento |
| HU03 | Registro de pago y generación de ticket | Captura Yape (JPG, PNG o PDF de hasta 8 MB), validación en caja y ticket con código único |
| HU04 | Venta presencial en taquilla | Ítems, total automático, método de pago y sede del cajero |
| HU05 | Asignación y validación de unidad de flota | Solo unidades disponibles de la sede; tickets de un solo uso |
| HU06 | Gestión de mantenimiento de flota | Registro, repuestos, historial y alerta preventiva |
| HU07 | Arqueo y cierre de caja | Apertura, movimientos, cierre y desglose de efectivo y Yape |
| HU08 | Reportes administrativos | Por periodo, sede, cajero y método de pago; cuadre diario; exportación a PDF |
| HU09 | Reglas de caja por sede y reasignación de cajeros | Lecturas de contador obligatorias solo en sedes con flota |

El detalle de los criterios de aceptación está en [historias_usuario.md](historias_usuario.md) y en los issues del repositorio.

## Tecnologías

- **Backend:** Python 3.12, Flask 3 (app factory y blueprints), Flask-SQLAlchemy, Flask-WTF (CSRF), Flask-Limiter y Authlib (Google OAuth).
- **Base de datos:** PostgreSQL 16 (SQLite para desarrollo sin conexión).
- **Frontend:** plantillas Jinja2, Tailwind CSS y JavaScript sin frameworks.
- **Servidor:** Waitress, detrás del proxy de Render.
- **Archivos:** almacenamiento local o en la nube (S3, Cloudflare R2 o Cloudinary) para las capturas de pago.
- **PDF:** fpdf2 para los reportes; el ticket se imprime desde el navegador.
- **Pruebas:** pytest, Katalon Recorder (Selenium IDE), Apache JMeter y SonarQube Cloud.
- **Contenedores:** Docker y Docker Compose.

## Arquitectura

El sistema sigue el patrón **Modelo-Vista-Controlador con una capa de servicios**:

```
app/
├── models/        Modelo: clases SQLAlchemy (usuarios, reservas, flota, caja, tickets...)
├── views/         Vista: plantillas Jinja2
├── static/        CSS (Tailwind y accesibilidad), JavaScript e imágenes
├── controllers/   Controlador: blueprints de Flask (rutas, permisos y respuestas)
├── servicios_*.py Servicios: lógica de negocio reutilizable (comprobantes, tickets,
│                  cuadre, entradas, reportes y PDF)
├── pruebas/       Casos de prueba funcionales y su motor de ejecución
├── esquema.py     Agrega columnas nuevas a una base de datos existente
└── seed.py        Datos iniciales (roles, sedes, flota y turnos)
tests/             Pruebas de pytest
servidor.py        Arranque con Waitress (producción)
run.py             Arranque con el servidor de desarrollo de Flask
```

## Accesibilidad

Todas las páginas públicas incluyen un panel de accesibilidad (WCAG 2.2 AA) con fuente legible, espaciado de texto, alineación a la izquierda, tamaño de texto, colores alternativos, alto contraste, escala de grises, pausa de animaciones, ocultar imágenes, resaltado de enlaces, cursor grande, guía de lectura y un narrador de imágenes con la Web Speech API. Las páginas públicas no tienen errores en el validador del W3C ni en WAVE, y obtienen 100 de accesibilidad en PageSpeed Insights.

## Instalación local

1. Clonar el repositorio y crear el entorno virtual:

   ```bash
   git clone https://github.com/Jeanoss1/Web---Dino.git
   cd Web---Dino
   python -m venv venv
   venv\Scripts\activate        # Windows  (Linux/macOS: source venv/bin/activate)
   pip install -r requirements.txt
   ```

2. Crear un archivo `.env` en la raíz con, al menos:

   | Variable | Para qué sirve |
   |---|---|
   | `DATABASE_URL` | Conexión a PostgreSQL |
   | `SECRET_KEY` | Clave para firmar la sesión |
   | `CAJERO_CORREO`, `CAJERO_CONTRASENA` | Cajero inicial que crea la semilla |
   | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Inicio de sesión con Google (opcional) |
   | `STORAGE_PROVIDER` y las variables de S3, R2 o Cloudinary | Guardar las capturas en la nube (opcional; por defecto, en `uploads/`) |
   | `PRUEBAS_DATABASE_URL` | Base de datos aparte para las pruebas (opcional) |

   El archivo `.env` no se sube al repositorio.

3. Crear el primer administrador e iniciar el sistema:

   ```bash
   python crear_admin.py
   python servidor.py            # http://localhost:8000 (variable PUERTO para cambiarlo)
   ```

   Al arrancar se crean las tablas, se agregan las columnas nuevas y se cargan los datos iniciales.

Con Docker: `docker compose up --build` levanta la aplicación y PostgreSQL 16.

## Pruebas

```bash
python -m pytest -q
```

La suite ejecuta 121 casos funcionales (CP-01-01 a CP-09-07 y los casos de los criterios agregados) sobre una base de datos de pruebas aparte (`dino_park_pruebas`), que se vacía al inicio. La base de datos principal nunca se modifica.

## Despliegue

El sistema se publica en **Render** (servicio web con Python y base de datos PostgreSQL 16). Render vuelve a desplegar cada vez que se actualiza la rama `main`.

## Equipo

- Altamirano Sanchez, J.
- Cajo Mejía, A.
- Fustamante Vasquez, E.
- Gonzales Rafael, J.
- Ramírez Vasquez, T.
