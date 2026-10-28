# Historias de Usuario - Dino Park



## HU01 - Gestión de usuarios y autenticación

**Como** cliente/usuario del sistema
**Quiero** poder registrarme, iniciar sesión y gestionar mi cuenta
**Para** acceder a los servicios del parque Dino Park

### Criterios de Aceptación

- [ ] El sistema debe permitir registrar nuevos clientes con nombres, apellidos, DNI, teléfono, correo y contraseña
- [ ] La contraseña debe tener al menos 8 caracteres y coincidir con su confirmación
- [ ] Debe existir aceptación obligatoria de términos y declaración
- [ ] No se permiten correos ni DNIs duplicados
- [ ] Los usuarios pueden iniciar sesión con correo o DNI
- [ ] Soporte para inicio de sesión con 'Recordarme' (sesión persistente)
- [ ] Las cuentas desactivadas no pueden iniciar sesión
- [ ] Debe existir funcionalidad de cerrar sesión
- [ ] Debe haber control de acceso por roles (cliente, cajero, administrador)
- [ ] Los clientes que se registran con Google deben completar su perfil (DNI y teléfono) antes de reservar


## HU02 - Catálogo, flota y reservas

**Como** cliente
**Quiero** consultar el catálogo, flota de atracciones y reservar turnos
**Para** poder disfrutar de las atracciones del parque

### Criterios de Aceptación
- [ ] El sistema debe listar las sedes activas
- [ ] Se debe poder visualizar la flota por sede con sus unidades disponibles
- [ ] Se debe poder filtrar la flota por tipo de atracción
- [ ] Se deben mostrar los turnos disponibles por unidad y fecha
- [ ] Las fechas deben mostrarse en formato DD-MM-AAAA
- [ ] Se debe permitir reservar una o más atracciones en una misma reserva
- [ ] No se pueden reservar turnos ya ocupados
- [ ] No se pueden reservar turnos de unidades en mantenimiento
- [ ] Un cliente solo puede ver y gestionar sus propias reservas
- [ ] Se debe permitir cancelar reservas
- [ ] Se debe mostrar duración y horario de los turnos


## HU03 - Comprobantes de pago

**Como** cliente
**Quiero** subir mi comprobante de pago (Yape, transferencia)
**Para** que el cajero valide mi reserva

### Criterios de Aceptación
- [ ] Se debe permitir subir comprobante en formato imagen (JPG, PNG) o PDF
- [ ] El tamaño del archivo debe tener límite (máx 8 MB)
- [ ] No se aceptan archivos renombrados con extensión falsa
- [ ] Un cliente puede reutilizar un comprobante subido anteriormente en otra reserva propia
- [ ] No se puede subir comprobante a una reserva ya confirmada o cancelada
- [ ] Solo puede haber un comprobante en revisión a la vez por reserva
- [ ] Un cliente solo puede ver sus propios comprobantes
- [ ] El cajero puede aceptar o rechazar el pago
- [ ] Al rechazar, es obligatorio indicar el motivo
- [ ] No se puede aceptar una reserva sin comprobante


## HU04 - Ventas de tienda

**Como** cajero
**Quiero** registrar ventas de productos de la tienda
**Para** cobrar y gestionar las compras

### Criterios de Aceptación
- [ ] Se debe permitir registrar ventas con uno o más items
- [ ] Se debe validar que existan items en la venta
- [ ] Se debe validar que el precio sea mayor a 0
- [ ] Se debe poder pagar una venta con diferentes métodos (efectivo, Yape, etc.)
- [ ] No se puede pagar una venta dos veces
- [ ] Es obligatorio indicar el método de pago
- [ ] No se puede pagar una venta inexistente


## HU06 - Mantenimiento de unidades

**Como** administrador/cajero con permisos
**Quiero** gestionar el mantenimiento de las unidades de atracción
**Para** mantener la flota en buen estado

### Criterios de Aceptación
- [ ] Se puede registrar un mantenimiento preventivo/correctivo a una unidad
- [ ] Es obligatorio indicar el tipo de mantenimiento
- [ ] Se debe poder asociar repuestos utilizados al mantenimiento
- [ ] No se puede usar repuestos sin stock suficiente
- [ ] No se puede registrar mantenimiento a una unidad inexistente
- [ ] No se puede reservar una unidad que se encuentra en mantenimiento
- [ ] Se puede finalizar un mantenimiento en curso
- [ ] No se puede finalizar un mantenimiento dos veces ni uno inexistente
- [ ] Se debe llevar el historial de mantenimientos por unidad
- [ ] Se debe poder consultar repuestos que necesitan reposición


## HU07 - Caja (apertura/cierre/movimientos)

**Como** cajero
**Quiero** gestionar la caja de mi sede
**Para** llevar el control de ingresos y egresos

### Criterios de Aceptación
- [ ] Se puede abrir caja indicando el monto inicial
- [ ] No se puede abrir dos cajas simultáneas en la misma sede/sesión según reglas
- [ ] Se pueden registrar ingresos y egresos con concepto
- [ ] Los movimientos deben tener tipo válido (ingreso, egreso)
- [ ] No se permiten montos cero, negativos o no numéricos
- [ ] No se pueden registrar movimientos con la caja cerrada
- [ ] Se puede cerrar la caja indicando el monto final
- [ ] El cierre se guarda con su detalle
- [ ] Después del cierre, la caja queda cerrada y no se permiten más movimientos
- [ ] No se puede cerrar una caja ya cerrada


## HU08 - Permisos por rol/sede

**Como** administrador
**Quiero** controlar el acceso según rol y sede
**Para** garantizar la seguridad del sistema

### Criterios de Aceptación
- [ ] Los cajeros asignados a una sede con flota solo ven flota, no entradas
- [ ] Los cajeros asignados a una sede sin flota (solo entradas) solo ven entradas, no flota
- [ ] El acceso a funcionalidades debe estar restringido según el rol del usuario


## HU09 - Reglas de caja por sede y reasignación de cajeros

**Como** administrador
**Quiero** reasignar cajeros entre sedes con reglas de negocio
**Para** mantener el control operativo

### Criterios de Aceptación
- [ ] Se puede reasignar la sede de un cajero sin caja abierta
- [ ] No se puede reasignar la sede de un cajero con caja abierta
- [ ] En sedes con flota, es obligatorio registrar las lecturas de inicio de unidades para abrir caja
- [ ] En sedes con flota, es obligatorio registrar las lecturas de cierre de unidades para cerrar caja
- [ ] En sedes sin flota (solo entradas), no se exigen lecturas de unidades para abrir/cerrar caja
- [ ] El cambio de sede solo es posible después de cumplir con las lecturas completas cuando aplique

---

*Generado a partir de los casos de prueba del proyecto Dino Park.*

