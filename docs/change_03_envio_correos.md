# Cambio 3 · email-sending

> Fuente para el futuro cambio OpenSpec `email-sending`. Contexto en [project_overview.md](project_overview.md) y [architecture.md](architecture.md).
> Depende de [platform-base](change_00_plataforma_base.md), del frontend aprobado y del outbox implementado en [backend](change_02_backend.md).

## 1. Objetivo

Completar el flujo de reclamación mediante la tarea de envío del único worker del backend. Consumir los registros de outbox creados al confirmar y enviar **uno por uno, con un único intento por correo y sin reintentos ni reenvíos**.

El éxito significa que la operación de envío terminó sin error y se registró. No garantiza recepción final ni que desaparezca toda incertidumbre ante un corte de comunicación.

## 2. Alcance y reglas definitivas

- **RN-04:** solo Uber Eats y Just Eat generan correo. Glovo se sigue sin correo.
- **RN-05:** dejar **al menos 30 segundos entre el inicio de dos intentos consecutivos**, incluidos los fallidos. Intervalo global del remitente, persistente ante reinicios y solapamientos de revisión; no una pausa independiente por réplica.
- El único worker comparte código e imagen con la API y realiza también importaciones. PostgreSQL garantiza exclusión mutua con `pg_advisory_lock` y `FOR UPDATE SKIP LOCKED`, y el intervalo global vive en una fila PostgreSQL (ADR-13); no se añade otro servicio ni broker.
- Mantener responsividad de las tareas: la espera del siguiente envío no debe impedir gestionar importaciones o pausa. No mantener una transacción de confirmación abierta mientras se envía correo.
- **RN-08:** hasta conocer los destinatarios reales, solo se permite un destinatario de prueba configurado. Pruebas en entorno separado, con datos, almacenamiento y métricas propios.
- **RN-12:** un intento finalizado sin error pasa a Enviado y la incidencia a Reclamada. Si falla o no puede verificarse el resultado, pasa a Error y la incidencia a Error de envío. No volver a enviar, automática ni manualmente, en v1.
- **RN-14:** plantilla única más order ID validado. Asunto y cuerpo pendientes P-03; descripción libre e importes no se incluyen. El único dato variable del correo es el número de incidencia (Order ID). Ejemplo aportado por el administrador, no texto final: «Estimados socios Ubereats, remitimos el siguiente incidente No Incidente 458665 para su reclamación. Un saludo Macdonalds».
- Leer destinatario y contenido autorizados en el outbox; no sustituirlos por la configuración vigente al enviar. Un correo sin configuración autorizada válida no se envía.
- Remitente: buzón institucional. Protocolo y autenticación pendientes P-02. Secretos en gestor de secretos, nunca en outbox, código, logs ni documentación.
- Pausa/reanudación global por administrador, persistente. Pausar impide iniciar otro correo; no cancela uno iniciado ni deshace confirmaciones.
- Consulta de cola con pendientes, en curso, enviados, errores y motivos; historial y auditoría. El frontend se integra con las operaciones aprobadas, sin añadir botones de reintentar.

## 3. Estados y recuperación

| Estado de correo | Transición | Efecto |
|---|---|---|
| Pendiente | A Enviando | Registrar duraderamente el inicio del único intento antes de llamar al servicio de correo |
| Enviando | A Enviado | Operación finalizada sin error; registrar resultado y actualizar incidencia/historial |
| Enviando | A Error | Fallo o resultado no verificable; registrar motivo y actualizar incidencia/historial |
| Enviado | Terminal | No se reenvía |
| Error | Terminal | No se reintenta ni se devuelve a Pendiente |

Antes de invocar el servicio se registra que el intento comenzó. Tras reiniciar, los que permanecían Pendientes pueden continuar; un registro Enviando cuyo resultado no se puede verificar termina en Error, sin nuevo envío. Si no es posible registrar el resultado por caída de PostgreSQL, no se vuelve a invocar el servicio: la recuperación resuelve el estado conservadoramente.

Un Error por interrupción puede corresponder a un mensaje aceptado externamente; mostrar que su resultado no se pudo verificar y no afirmar que nunca llegó. Enviado representa éxito de la operación, no prueba de entrega. No se crea un estado adicional de reintento ni una promesa absoluta de entrega sin duplicados.

Un lote pasa a Completado cuando todos sus correos están Enviado o Error. Mostrar totales de éxito y fallo; Completado no significa éxito total. Los lotes sin correo pueden completarse desde el cambio 2.

## 4. Entorno de prueba y futura activación real

Configurar un único destinatario de prueba. Todos los correos de Uber Eats y Just Eat del entorno de prueba van a él; Glovo sigue sin generar correo. El entorno y sus cifras se identifican como pruebas y se aíslan de producción. No se trasladan lotes ni outbox a producción, ni se reenvían allí los registros de prueba.

Los datos reales se importarán y confirmarán independientemente en producción. Antes de activar envío real se necesitan destinatarios reales, asunto/cuerpo aprobados, acceso al buzón y límites adicionales verificados, más aprobación explícita del administrador. No convertir la activación en un cambio silencioso de destinatario de correos ya confirmados.

La configuración inicial debe ser segura y no permitir destinatarios reales por defecto. Estado de pausa y configuración aprobada se conservan entre reinicios; reiniciar no autoriza destinos ni reactiva errores. En local se utiliza captura SMTP sin envío a proveedores.

## 5. Requisitos funcionales

| ID | Requisito | Criterio de aceptación |
|---|---|---|
| RF-11 | Consumo asíncrono de un correo por incidencia elegible | Un intento por registro, secuencial, separado al menos 30 s; Glovo excluido |
| RF-12 | Pruebas seguras y aisladas | Solo destinatario de prueba; métricas/datos separados de producción |
| RF-13 | Estados, historial y error sin reintentos | Enviado o Error registrados; fallos e interrupciones no provocan reenvío |
| RF-14 | Seguimiento y pausa/reanudación | El administrador consulta motivos y controla nuevos intentos; permiso comprobado en API |

RF-14 es obligatorio para el control operativo. Se conserva su identificador, sustituyendo el carácter opcional anterior. RNF aplicables: 02, 03, 04, 05, 10, 12, 13 y 15.

## 6. Escenarios y pruebas previstas

| ID | Dado / Cuando | Entonces |
|---|---|---|
| E-09 | Correos Uber Eats/Just Eat del entorno de prueba | Solo llegan al destinatario de prueba; no aparecen en métricas de producción |
| E-10 | Un intento falla | Error con motivo e incidencia Error de envío; ningún nuevo intento |
| MAIL-01 | Dos o más pendientes | Inicios separados por al menos 30 s, también si el anterior falla |
| MAIL-02 | Se pausa con un correo iniciado | Ese intento puede terminar; no se inicia otro hasta reanudar |
| MAIL-03 | Se reinicia con pendientes y un Enviando no verificable | Pendientes continúan respetando intervalo; Enviando termina Error y no se reenvía |
| MAIL-04 | Dos revisiones de worker se solapan | Un solo propietario ejecuta el trabajo y el espaciado sigue siendo global |
| MAIL-05 | Cambia plantilla o destinatario después de confirmar | Se conserva el contenido/destino autorizado del outbox |
| MAIL-06 | Operación de envío termina sin error | Enviado, incidencia Reclamada e historial/auditoría registrados |
| MAIL-07 | Servicio acepta pero se interrumpe antes de registrar éxito | Sin resultado verificable se registra Error al recuperar, sin volver a enviar |
| MAIL-08 | Todos los correos terminan, alguno en Error | Lote Completado con totales diferenciados |
| MAIL-09 | Usuario sin permisos intenta pausar/reanudar | FastAPI deniega acceso |
| MAIL-10 | Destino real no autorizado o configuración pendiente | No se envía a un proveedor real |
| MAIL-11 | Hay un lote solo de Glovo | No hay registros ni intentos de correo |

TDD obligatorio para outbox: exclusión, espaciado global, pausa, estados terminales, ausencia de reintentos, interrupciones y aislamiento. Integración con PostgreSQL real y captura SMTP; flujo completo XLSX → Blob/Azurite → staging → revisión → confirmación → envío de prueba.

## 7. Fuera de alcance y definición de hecho

Fuera de alcance: reintentos automáticos, reenvíos manuales, cancelación posterior a confirmar, lectura de respuestas, correo Glovo y destinatarios reales aún no definidos. Resolver P-01 a P-03 antes de ejecutar pruebas de envío con el buzón; verificar límites adicionales sin recuperar cuotas del prototipo.

Hecho: pruebas del consumidor y flujo completo verificables, errores auditados y visibles, pausa operativa, intervalo de 30 s respetado y ningún mecanismo de reintento. El entorno de prueba acredita el funcionamiento sin presentar sus métricas como reclamaciones reales. La activación real queda condicionada a sus requisitos y aprobación.
