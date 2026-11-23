# Delivery Hub · Arquitectura y requisitos técnicos

> Complementa [project_overview.md](project_overview.md). Las decisiones aprobadas son obligatorias. Una propuesta o un punto **[por definir]** no se considera implementado.

## 1. Terminología y componentes

| Término | Definición |
|---|---|
| Frontend | React + TypeScript independiente del backend |
| Backend | Única aplicación Python modular con reglas de negocio y acceso a servicios |
| API | Proceso HTTP del backend ejecutado con FastAPI |
| Worker | Proceso del mismo backend para importación y envío |
| Tarea de importación / envío | Responsabilidades del único worker; no son servicios independientes |

**Dos bases de código, dos imágenes y tres servicios de aplicación:** frontend, API y worker. API y worker comparten imagen Python con distintos comandos de arranque. PostgreSQL y Blob son servicios de datos externos.

```text
Usuario -> Google / Easy Auth -> Frontend -> API FastAPI
                                              |    |
                                              v    v
                                             Blob PostgreSQL
                                              ^    ^
                                              |    |
                                              Worker unico -> Correo
```

El diagrama es lógico. Easy Auth protege los accesos correspondientes y FastAPI autoriza cada operación. El XLSX viaja directamente del navegador a Blob mediante permiso temporal de la API.

## 2. Stack y despliegue

| Área | Tecnología / decisión | Estado |
|---|---|---|
| Frontend | React + TypeScript, SPA en contenedor | Definido |
| API | Python + FastAPI, Pydantic y OpenAPI | Definido |
| Lectura XLSX | openpyxl en modo solo lectura, sin ejecutar macros ni evaluar fórmulas | Propuesta |
| Persistencia / migraciones | SQLAlchemy 2 y Alembic | Propuesta |
| Base de datos | Azure Database for PostgreSQL Flexible Server creado por Bicep, uno por entorno; PostgreSQL real local | Definido |
| Archivos | Blob Storage; Azurite local | Definido |
| Identidad de usuarios | Google mediante Easy Auth de Container Apps | Definido |
| Autorización | Middleware FastAPI, allowlist y permisos por rol | Definido |
| Trabajo asíncrono | Un worker permanente, sin broker adicional | Definido |
| Correo | Buzón institucional; protocolo y autenticación [por confirmar, P-02] | Remitente definido, acceso pendiente |
| Infraestructura | Azure Container Apps y Bicep | Definido |
| CI/CD | GitHub Actions | Definido |
| Observabilidad | OpenTelemetry, Azure Monitor y Application Insights | Definido |

El worker no expone ingress público y tiene una réplica permanente. La exclusión mutua PostgreSQL evita ejecución simultánea del mismo trabajo, incluso durante solapamientos de revisiones. Los trabajos de importación se registran en el lote de forma duradera; no dependen de la memoria de una petición HTTP. El intervalo global de envío se conserva ante reinicios. La API puede escalar sin multiplicar envíos.

**Exclusión mutua (ADR-13):** el worker toma un `pg_advisory_lock` que lo hace único propietario del bucle de trabajo; una revisión solapada espera o no arranca el bucle. Cada tarea se reclama además por fila con `SELECT … FOR UPDATE SKIP LOCKED`. El intervalo global de 30 s se guarda en una fila de PostgreSQL (`last_attempt_started_at`), leída y actualizada bajo bloqueo antes de iniciar cada intento.

## 3. Responsabilidades y flujo

| Componente | Responsabilidad |
|---|---|
| Frontend | Subida, vista previa, confirmación, seguimiento, resultados, panel y administración |
| API | Autorización, permisos de subida, solicitud/consulta de procesamiento, confirmación y operaciones de negocio |
| Worker | Leer y clasificar XLSX en staging; consumir outbox y enviar de forma espaciada |
| Blob | XLSX temporal y original conservado de lotes confirmados |
| PostgreSQL | Lotes, staging, incidencias, outbox, historial, auditoría y configuración de negocio |
| Google + Easy Auth | Autenticación del usuario |
| Allowlist y roles | Autorización de la identidad y sus operaciones |

Flujo obligatorio: **XLSX → Blob → validación y staging → vista previa → confirmación → incidencias y outbox → envío**. La API registra la finalización de la subida y solicita su procesamiento; el worker puede descubrir trabajos pendientes tras reiniciar. El backend verifica pertenencia del lote, existencia e integridad del archivo; no acepta referencias arbitrarias del navegador.

La vista previa se obtiene de staging. Validar y transformar antes de confirmar no crea incidencias definitivas. Solo la aprobación humana permite insertarlas junto a sus correos pendientes.

## 4. Decisiones de arquitectura

| ID | Decisión | Estado |
|---|---|---|
| ADR-01 | Un backend Python modular con API FastAPI y worker del mismo código | Definido |
| ADR-02 | Frontend React independiente; diseño aprobado antes de implementar lógica de negocio | Definido |
| ADR-03 | Frontend, API y worker en Container Apps con IaC Bicep | Definido |
| ADR-04 | PostgreSQL gestionado, incluyendo staging y outbox | Definido |
| ADR-05 | Google + Easy Auth + allowlist para acceso de usuarios | Definido; sustituye la decisión previa de login |
| ADR-06 | Incidencias, outbox, estado confirmado y auditoría en una transacción PostgreSQL; sin broker | Definido |
| ADR-07 | OpenTelemetry, Azure Monitor, Application Insights y GitHub Actions | Definido |
| ADR-08 | Un worker con réplica permanente y exclusión mutua PostgreSQL | Definido |
| ADR-09 | Un intento por correo, sin reintentos/reenvíos y mínimo global de 30 s entre inicios | Definido |
| ADR-10 | Pruebas en entorno separado con datos propios y destinatario de prueba | Definido |
| ADR-11 | Staging temporal; descarte solo explícito (cancelar o botón Cerrar sesión), sin caducidad automática | Definido; sustituye la caducidad de 60 min |
| ADR-12 | Easy Auth solo en el frontend, que reenvía `/api` a una API con ingress interno; la API confía en la identidad que reenvía el frontend | Definido |
| ADR-13 | Worker: `pg_advisory_lock` para un único propietario del bucle y `FOR UPDATE SKIP LOCKED` por fila; intervalo global en fila PostgreSQL | Definido |
| ADR-14 | Original revisado identificado por SHA-256; subida sin sobrescritura; copia a contenedor `confirmed` inmutable tras confirmar | Definido |
| ADR-15 | PostgreSQL Flexible Server creado por Bicep, uno por entorno; secretos en Key Vault con identidad administrada | Definido |
| ADR-16 | Contrato frontend/backend como OpenAPI versionado en `docs/api/openapi.yaml`; el backend debe coincidir con la versión aprobada | Definido |

Se mantienen identidades administradas Azure para acceso de servicios a Blob y secretos. No determinan el proveedor de login de usuarios. Nuevos servicios o cambios incompatibles requieren ADR.

## 5. Datos, clasificación y confirmación

Entidades: lotes, staging, incidencias, outbox, historial, auditoría, autorizaciones/roles, sucursales y proveedores. El diseño detallado pertenece al cambio 2.

- **Unicidad:** restricción PostgreSQL sobre proveedor + order ID. La sucursal queda fuera; es una regla definitiva.
- **Clasificación excluyente:** nueva, duplicada, en conflicto o con error. Duplicado: misma clave y mismos campos relevantes. Conflicto: misma clave con diferencias. Comparación y repeticiones internas en el cambio 2.
- **XLSX:** una hoja; tres encabezados y valores obligatorios; cinco columnas opcionales según la visión general. Solo convertir sucursal y proveedor a minúsculas.
- **Importes:** euros, representación decimal y precisión conservada, sin imponer dos decimales. El tipo concreto debe verificarse con muestras antes de fijar el esquema. Ausente no significa cero.
- **Fechas:** incidencia con fecha y hora opcional (`YYYY-MM-DD` o `YYYY-MM-DD HH:MM`, hora local Europe/Madrid); si el origen no trae hora, no se inventa. Distinguir reclamación y recuperación. Marcas temporales de eventos almacenadas con criterio UTC y presentadas en Europe/Madrid.
- **Atomicidad:** incidencias, outbox, estado confirmado y auditoría se crean juntos o ninguno. Glovo y altas manuales sin correo no requieren outbox.
- **Idempotencia y concurrencia:** la confirmación repetida devuelve su resultado sin nuevos registros. Controlar simultaneidad sobre el lote y unicidad entre lotes.
- **Versión autorizada:** vista previa y confirmación identifican archivo, destinatario y plantilla. El outbox conserva el contenido autorizado; editar configuración no lo cambia silenciosamente.

Blob no forma parte de la transacción PostgreSQL. Verificar y proteger la versión del original revisado antes de confirmar y poder comprobar después su conservación. Una discrepancia debe registrarse y alertarse, sin fingir atomicidad distribuida ni sustituir el original por otro archivo.

**Original revisado (ADR-14):** la SAS de subida concede solo crear, nunca sobrescribir, y apunta a un contenedor temporal (`uploads`). El worker calcula el SHA-256 del archivo, lo guarda en el lote y la vista previa lo identifica junto con la versión del blob. La confirmación exige ese hash. Tras la transacción PostgreSQL, el worker copia el original a un contenedor `confirmed`, con nombre determinista por lote (copia idempotente), y verifica el hash; hasta verificarla, la limpieza de temporales no borra el blob de un lote Confirmado. Una discrepancia se registra y alerta. `confirmed` tiene inmutabilidad a nivel de contenedor; su periodo de retención se fija con P-05 y hasta entonces no se concede permiso de borrado a ninguna identidad de la aplicación. Azurite no soporta políticas de inmutabilidad: en local el adaptador `StorageService` aplica la misma regla por código.

## 6. Temporalidad y limpieza

Cancelar un lote o pulsar el botón **Cerrar sesión** de la aplicación descarta los lotes no confirmados **del usuario**. El botón llama a la API para descartarlos y no cierra la sesión de Google/Easy Auth ni redirige. **No hay caducidad automática**: un lote sin confirmar permanece En revisión hasta que se confirma o descarta, incluso tras un cierre inesperado del navegador o una sesión que termina por sí sola; el usuario puede retomarlo. Si la llamada de descarte falla, se informa y el lote sigue En revisión. **Cada usuario tiene como máximo un lote sin confirmar** (estados Subido, Procesando o En revisión), garantizado en PostgreSQL también bajo concurrencia; para subir otro archivo hay que confirmar o descartar el actual. Un lote Rechazado no cuenta. Descartar debe ser posible en cualquiera de esos tres estados, para que un procesamiento atascado no bloquee al usuario.

Al descartar se impide confirmar y se eliminan archivo y staging. Si el borrado físico falla, debe quedar observable y completarse posteriormente, sin declararlo realizado. Cadencia y plazo máximo de limpieza física [por definir, P-05]. No se conserva contenido del lote descartado; la auditoría mínima no incluye sus filas ni el XLSX.

Confirmación y limpieza se coordinan sobre el estado del lote en PostgreSQL. Si una confirmación válida obtiene el control primero, la limpieza no borra sus datos. Si ya se descartó, confirmar se rechaza. Un fallo transaccional no deja incidencias parciales y permite conservar staging mientras el lote siga En revisión.

El XLSX confirmado se conserva enlazado a lote, usuario y fecha, con retención [por definir]. Tras una confirmación exitosa se limpia el staging, conservando las incidencias y el resultado registrado. La limpieza de temporales nunca elimina originales confirmados.

## 7. Estados

### Lote

| Estado | Significado / transición |
|---|---|
| Subido | Archivo recibido; pasa a Procesando |
| Procesando | Validación y staging; pasa a En revisión o Rechazado |
| En revisión | Vista previa; pasa a Confirmado o Descartado |
| Rechazado | Estructura inválida; limpiar contenido temporal |
| Descartado | Cancelación o botón Cerrar sesión; no confirmable, limpiar contenido temporal |
| Confirmado | Transacción completada; pasa a Completado |
| Completado | Todos los correos terminaron Enviado o Error; ninguno pendiente ni en curso |

Un lote sin correos puede completarse al confirmar. Completado no significa éxito de todos los envíos: se muestran totales. Rechazado y Descartado describen el resultado observable, sin exigir conservar el contenido temporal.

### Incidencia

| Estado | Significado / transición |
|---|---|
| Importada (sin correo) | Glovo o alta manual sin correo; puede marcarse Reclamada por vía externa |
| Pendiente de envío | Confirmada con outbox; pasa a Reclamada o Error de envío |
| Reclamada | Envío sin error o reclamación manual registrada; admite Resuelta o Rechazada |
| Error de envío | Fallo o resultado no verificable; sin vuelta a Pendiente de envío en v1 |
| Resuelta / Rechazada | Resultado registrado; admite corrección manual auditada |

### Correo

| Estado | Significado / transición |
|---|---|
| Pendiente | Creado al confirmar; pasa a Enviando |
| Enviando | Único intento iniciado; termina en Enviado o Error |
| Enviado | Operación finalizada sin error; terminal |
| Error | Fallo o resultado no verificable, con motivo; terminal y sin reintento |

Tras una interrupción, un correo que quedó Enviando termina en Error si no puede verificarse el resultado; no vuelve a enviarse. Los que seguían Pendientes pueden continuar respetando pausa e intervalo global.

Pausar/reanudar controla nuevos intentos sin cancelar el iniciado ni modificar estados terminales. No hay reversión posterior a confirmar. Enviado no acredita entrega final y Error por interrupción no demuestra que el correo no se recibiera.

## 8. Identidad, permisos y secretos

Easy Auth autentica con Google. FastAPI utiliza una identidad procedente del mecanismo confiable de Easy Auth y comprueba la allowlist; no confía en cabeceras arbitrarias ni permite eludir autenticación en Azure. Los valores e identificador estable de la allowlist se concretan antes de implementar identidad.

| Acción | Administrador | Gerente global, si se habilita |
|---|---|---|
| Subir, revisar, cancelar antes de confirmar y confirmar | Sí | No |
| Alta manual, resultados y sus correcciones | Sí | No |
| Pausar / reanudar cola | Sí | No |
| Activar envío real tras resolver sus requisitos | Sí | No |
| Consultar incidencias, historial y panel | Sí | Sí |

**Transporte de identidad (ADR-12):** Easy Auth (Google) se configura solo en la Container App del frontend, con autenticación obligatoria. El frontend sirve la SPA y reenvía `/api/*` a la API, que tiene **ingress interno** (accesible solo dentro del entorno de Container Apps) y sin Easy Auth propio. El proxy del frontend reenvía únicamente las cabeceras de identidad de Easy Auth (`X-MS-CLIENT-PRINCIPAL*`), que Easy Auth sobrescribe y no acepta del cliente. FastAPI trata esa cabecera como confiable solo en el entorno Azure, rechaza con 401 las peticiones sin ella y comprueba después la allowlist. El worker no tiene ingress. El identificador estable de la allowlist (sub de Google o correo) se fija en P-07. En local, el adaptador de identidad de desarrollo sustituye a esta cabecera y no puede activarse en Azure (RNF-16). El permiso temporal de subida a Blob no pasa por el proxy; el CORS de Blob admite solo el origen del frontend.

Allowlist y roles forman una autorización coherente. Retirar una identidad impide acceso aunque su sesión Google continúe. La aplicación no crea cuentas Google ni guarda contraseñas. Administrador inicial configurado fuera del código. La allowlist, los roles, las sucursales y los proveedores los mantiene el equipo técnico con migraciones y configuración: la aplicación no tiene pantalla ni API para editarlos.

Secretos fuera de repositorio, logs y base de datos en claro: `.env` local excluido del versionado y Azure Key Vault con identidad administrada en Azure. `StorageService` permite Azurite y Blob por configuración. El permiso temporal de subida se limita al blob autorizado y no permite sustituir el original confirmado.

Mantener validación de archivos y límites explícitos. No exponer datos libres ni credenciales en logs. Clasificación de datos y obligaciones adicionales [por confirmar, P-11].

## 9. Correo y métricas por entorno

Solo el destinatario de prueba configurado está permitido hasta definir los reales. El entorno de prueba tiene base de datos y almacenamiento propios; sus métricas se identifican como pruebas. No se promueven lotes u outbox a producción.

El intervalo mínimo de 30 s es global al remitente entre inicios de intentos, incluidos los que fallan. No hay pausas aleatorias ni cuotas heredadas del prototipo. Límites adicionales del buzón [por verificar]. No se reintentan ni reenvían correos.

Remitente institucional; acceso pendiente P-02. Plantilla única más order ID, asunto/cuerpo pendientes P-03. No incorporar descripción libre sin decisión explícita. Envío real requiere destinatarios, plantilla y configuración validados y activación explícita del administrador.

Las métricas separan correo y Glovo y registran importes recuperados explícitos. Los importes desconocidos no son cero. Criterios temporales y agregación con datos incompletos [por definir, P-04]. Agregaciones en PostgreSQL, sin almacén analítico adicional.

## 10. Requisitos no funcionales

| ID | Requisito | Verificación prevista |
|---|---|---|
| RNF-01 | Vista previa de 300–600 filas sin truncado silencioso | Muestras y límites; objetivo temporal [por definir] |
| RNF-02 | Un intento por correo y resultado registrado, sin reintentos | Estados terminales, exclusión mutua, fallos e interrupciones |
| RNF-03 | Reinicios conservan datos y trabajo pendiente | Recuperación; envíos iniciados no verificables terminan en Error |
| RNF-04 | Google, Easy Auth, allowlist, roles y secretos fuera del código | Acceso autorizado y rechazo del resto |
| RNF-05 | Auditoría de acciones y cambios | Usuario o actor sistema, fecha, objeto y resultado |
| RNF-06 | Temporalidad y conservación diferenciadas | Descarte explícito, limpieza y original confirmado protegido; sin caducidad automática |
| RNF-07 | UI en español y errores comprensibles | Revisión con administrador |
| RNF-08 | Escritorio, teclado y contraste | Revisión de accesibilidad |
| RNF-09 | Separación simple de responsabilidades | API escalable, worker único y consistencia PostgreSQL |
| RNF-10 | Logs, alertas, backups y restauración | Restauración documentada; retención, RPO y RTO [por definir] |
| RNF-11 | Container Apps y PostgreSQL gestionado externo | Despliegue verificado |
| RNF-12 | Destinatario autorizado, remitente institucional e intervalo de 30 s | Destino, pausa y espaciado |
| RNF-13 | Criterio de fechas explícito | Hora de incidencia solo si viene en el origen, interpretada en Europe/Madrid; eventos del sistema en UTC y mostrados en Europe/Madrid |
| RNF-14 | Entorno local reproducible | Compose con PostgreSQL, Azurite, frontend, API, worker y captura SMTP |
| RNF-15 | Mismo código, configuración por entorno | Interfaces de almacenamiento, identidad y correo |
| RNF-16 | Identidad de desarrollo imposible de activar en Azure | Arranque rechazado fuera de local si está activa |

## 11. Desarrollo local y calidad

| Servicio | Local | Azure |
|---|---|---|
| PostgreSQL | Contenedor real persistente | Servicio gestionado |
| Blob | Azurite persistente | Blob Storage |
| Aplicación | Frontend, API y un worker en Compose | Tres servicios Container Apps |
| Identidad | Adaptador explícito de desarrollo con rol configurable | Google + Easy Auth + allowlist |
| Correo | Captura SMTP local, sin proveedores reales | Destinatario de prueba en entorno separado hasta aprobar envío real |
| Observabilidad | Consola o colector local, detalle propuesto | Azure Monitor y Application Insights |

La configuración selecciona adaptadores, manteniendo iguales las reglas de negocio. La identidad de desarrollo falla al arrancar en Azure. `.env.example` documentará variables sin secretos. Migraciones versionadas y reversibles, sin deshacer importaciones confirmadas como operación de usuario.

SDD con OpenSpec. TDD para clasificación/deduplicación, confirmación atómica/idempotente y outbox sin reintentos. Pruebas previstas: unitarias, integración con PostgreSQL y Azurite reales, concurrencia, XLSX anonimizados y extremo a extremo en entorno de prueba. Los ejemplos del cambio 1 sirven para revisar diseño, sin sustituir integración real del cambio 2.

Cada requisito enlaza con un escenario. CI ejecutará lint, pruebas e imágenes antes de desplegar; revisión, cobertura y escaneo [por definir]. Hecho exige especificación cumplida, verificaciones del cambio, observabilidad, documentación coherente y ausencia de secretos. El cambio 1 exige aprobación explícita de diseño y flujos.

## 12. Cambios y reglas de trabajo

Solo existen **0 platform-base, 1 frontend, 2 backend y 3 email-sending**. El cambio 2 crea outbox pero no envía; el 3 incorpora envío. La auditoría se añade con cada operación.

Fuentes Markdown en español. Futuros specs formales OpenSpec, código, identificadores y commits en inglés. Un artefacto pendiente no es capacidad implementada. No introducir servicios nuevos sin ADR. Los pendientes P-01 a P-12 se centralizan en la visión general; no se convierten en restricciones implícitas ni reabren decisiones aprobadas.
