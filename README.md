# Dino Park

Sistema web (Flask + PostgreSQL) para el alquiler de dinosaurios, carros y motos para niños en centros
comerciales de Cajamarca. Sedes: **Real Plaza**, **Mega Plaza** y **Hoyos Rubio** (inactiva hasta su apertura).

Arquitectura MVC: `app/models` (datos), `app/views` (plantillas), `app/controllers` (Blueprints delgados) y
`app/services` (lógica de negocio).

## Instalación

Requisitos: Python 3.10+ y PostgreSQL con una base vacía llamada `dino_park_db`.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # Linux/Mac: cp .env.example .env   -> luego edita los valores
```

Edita `.env` (nunca lo subas a git): `SECRET_KEY`, `DATABASE_URL`, `YAPE_NUMERO`.
Genera la clave con `python -c "import secrets; print(secrets.token_hex(32))"`.

```bash
flask --app run db upgrade        # crea las tablas con las migraciones
flask --app run seed --demo       # datos de prueba (sin --demo: solo datos base, sin ventas de ejemplo)
python run.py                     # http://127.0.0.1:5000
```

Cuando cambies un modelo: `flask --app run db migrate -m "descripción"` y luego `flask --app run db upgrade`.

## Cuentas de prueba (contraseña: la de `SEED_PASSWORD`, por defecto `Dino2026!`)

| Rol | Correo | Detalle |
|---|---|---|
| Administrador | admin@dinopark.pe | Todas las sedes |
| Cajero | cajero1.realplaza@dinopark.pe | Cajero 1 Real Plaza · tiempo completo (8 h) |
| Cajero | cajero2.realplaza@dinopark.pe | Cajero 2 Real Plaza · medio tiempo (4 h) |
| Cajero | cajero1.megaplaza@dinopark.pe | Cajero 1 Mega Plaza · tiempo completo |
| Cajero | cajero2.megaplaza@dinopark.pe | Cajero 2 Mega Plaza · medio tiempo |
| Cliente | cliente1@ejemplo.pe (DNI 70000001), cliente2, cliente3 | |

## Roles

- **Cliente**: se registra, ve la disponibilidad, reserva, paga por Yape, sube la captura y consulta el estado.
- **Cajero**: pertenece a UNA sede y a un tipo de turno (completo 8 h / medio 4 h). Valida pagos Yape
  (acepta o rechaza con motivo), registra ventas presenciales, controla los minutos de uso, abre y cierra caja.
  Solo ve datos de su sede.
- **Administrador**: todas las sedes; usuarios y cajeros, turnos semanales, flota, tarifas, sedes,
  mantenimiento, cuadre diario y reportes.

## Reglas del negocio

- **Tarifa única**: S/ 10 por 12 minutos para todas las atracciones (tabla `tarifas`, editable en *Tarifas*).
  Cada venta: `minutos = bloques × 12`, `total = bloques × precio`. El precio siempre lo pone el servidor.
- **Reserva**: `pendiente_pago → pago_en_revision → confirmada → completada`; también `rechazada` y `cancelada`.
  El cliente tiene 15 minutos (`MINUTOS_LIMITE_PAGO`) para subir la captura o la reserva se cancela y libera el horario.
- **Franjas**: el horario reservable de una unidad (bloques de 12 min entre 10:00 y 22:00, se generan por día).
  Una franja no puede reservarse dos veces (bloqueo de fila + índice único en la base de datos).
- **Turnos**: el *turno* es el horario laboral del cajero (8 h o 4 h). El administrador asigna cada semana
  (grilla, copiar/rotar la semana anterior o importar `.csv`/`.xlsx`).
- **Cuadre diario**: por sede y cajero compara minutos vendidos vs. usados y el efectivo esperado vs. contado,
  más el Yape. Marca alertas si la diferencia de minutos supera `TOLERANCIA_MINUTOS` (2) o si falta/sobra dinero.
- **Reportes**: por cajero (total, n.º de ventas, minutos, ticket promedio, horas trabajadas y ventas por hora),
  por sede, por tipo de atracción y método de pago; semanal, mensual o fechas personalizadas; exportables a Excel y PDF.

## Finalización automática y contadores

- **Alquiler**: al vender se guarda la hora de inicio y la de fin prevista (bloques × 12 min). Termina SOLO: un proceso en
  segundo plano (APScheduler, cada 30 s, se inicia con `python run.py`) lo finaliza aunque nadie tenga el navegador abierto, y
  además se finaliza al consultar (idempotente: nunca se suma dos veces). El cajero solo puede «finalizar antes» con un motivo.
  Con otro servidor (gunicorn) usa un solo proceso y `flask --app run finalizar-vencidos` en un cron cada minuto.
- **Contadores**: dinosaurios cuentan **minutos** (se suman al finalizar); carros y motos cuentan **encendidos** (+1 al iniciar).
  El administrador elige el tipo de contador de cada atracción (Flota) y las tolerancias (Tarifas).
- **Lecturas manuales**: al abrir caja el cajero anota la lectura inicial de cada atracción (se precarga la del último cierre;
  si difiere exige motivo y avisa al administrador) y al cerrar la lectura final. Se compara con el contador del sistema y con lo
  vendido (Reportes → Contadores, con exportación a Excel/PDF).
- **Voucher**: la pantalla del ticket imprime solo el voucher térmico (80 mm). En Chrome/Edge elige el papel de 80 mm de tu
  impresora térmica en el diálogo de impresión.

## Seguridad

Contraseñas con hash (werkzeug), sesión firmada con `SECRET_KEY`, rol leído de la base en cada petición,
protección CSRF (Flask-WTF), límite de intentos de login, capturas validadas por su contenido y guardadas
en `uploads/` con nombre aleatorio (fuera de `static/`), cabeceras de seguridad y cookies `HttpOnly` + `SameSite`.
En producción usa `APP_ENV=production`, `SESSION_COOKIE_SECURE=1` y un servidor WSGI (gunicorn/waitress).

## Pruebas

```bash
python -m pytest
```

Usan SQLite en memoria (no tocan tu base). Cubren login, permisos por rol en todas las rutas, aislamiento por sede,
reservas y pagos Yape, cálculo de precios, caja y cuadre, turnos y reportes.
