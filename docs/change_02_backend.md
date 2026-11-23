# Cambio 2 · backend

> Fuente para el futuro cambio OpenSpec `backend`. Contexto en [project_overview.md](project_overview.md) y [architecture.md](architecture.md).
> Depende de [platform-base](change_00_plataforma_base.md) y del diseño/contrato aprobados de [frontend](change_01_frontend.md).
> El envío se incorpora después en [email-sending](change_03_envio_correos.md).

## 1. Objetivo y alcance

Implementar la API FastAPI y la lógica de negocio del único backend Python: modelo y migraciones, permisos, ingesta mediante el worker compartido, clasificación, staging, confirmación, outbox, consultas, métricas, alta manual y registro de auditoría. Integrar el frontend aprobado con datos reales. No hay API ni pantalla de administración ni de consulta de auditoría: las gestiona el equipo técnico.

Al terminar, confirmar crea incidencias y correos pendientes, **pero no los envía**. El consumidor de correo pertenece al cambio 3. La auditoría se registra con cada operación desde su implementación.

## 2. Entrada XLSX y preparación

El navegador recibe un permiso temporal de subida y carga directamente el XLSX en Blob. La API registra el lote y la finalización de la subida; el único worker descubre el trabajo, verifica el archivo y lo procesa a staging. La vista previa se consulta mediante la API. No se implementa un worker de importación independiente. La API solo concede el permiso de subida si el usuario no tiene otro lote sin confirmar (Subido, Procesando o En revisión); en otro caso lo rechaza indicando el lote pendiente.

| Encabezado | Obligatorio en archivo y por fila |
|---|---|
| Proveedor | Sí |
| Order ID | Sí |
| Fecha y hora | Sí; fecha con hora opcional (ver reglas de lectura) |
| Sucursal | No; columna y celda pueden faltar |
| Importe a reclamar | No; columna y celda pueden faltar |
| Costos de proveedor | No; columna y celda pueden faltar |
| Total | No; columna y celda pueden faltar |
| Descripción | No; columna y celda pueden faltar |

Una sola hoja. Las ocho denominaciones anteriores son los encabezados reconocidos; no se exige que aparezcan las ocho columnas. La ausencia de un encabezado obligatorio rechaza el archivo entero. Un valor obligatorio ausente invalida esa fila, sin impedir preparar las demás.

Reglas de lectura:

- Conservar el original y su versión/huella; avisar si coincide con un archivo ya confirmado antes de continuar su preparación. El aviso no sustituye a la deduplicación.
- Convertir solo sucursal y proveedor a minúsculas. No recortar espacios, resolver alias, modificar order ID ni normalizar otros campos en v1.
- Reconocer proveedores `uber eats`, `just eat` y `glovo` tras esa conversión. Proveedor desconocido: error de fila.
- Sucursal ausente: válida y sin asignación. Sucursal proporcionada desconocida: error. El catálogo inicial debe estar disponible en este cambio, antes de probar importaciones. Catálogo facilitado por el administrador (2026-11-23): Palacio de hielo, Hortaleza, Plaza, Bravo, Manoteras, Plenilunio y Ermita; se guardan en minúsculas. Que una sucursal no aparezca en el archivo no es un error: solo lo es una sucursal proporcionada que no esté en el catálogo.
- Moneda euro. Conservar precisión decimal en lectura, staging, persistencia, API y exportación; no imponer redondeo a dos cifras ni cálculos binarios que alteren el valor.
- Importe a reclamar ausente: no es error por sí solo, no se inventa y no impide crear el outbox de una fila válida. **Importes (Importe a reclamar, Costos de proveedor y Total), regla resuelta:** si se proporcionan, deben ser números (decimales permitidos) y se conservan con el signo y el valor del origen, incluidos cero y negativos; no se valida su signo ni se corrigen. Se asumen válidos. El correo y el outbox no incluyen importes: solo el número de incidencia (Order ID). Una celda numérica nativa es válida; un texto, aunque parezca un número (`12,50 €`, `12.5`), es error de fila ("el importe debe ser numérico"); una celda vacía es ausente, no cero. La relación entre Total y otros importes sigue pendiente P-10.
- No ejecutar macros ni evaluar fórmulas. Un dato obligatorio representado mediante fórmula no se considera validado por asumir un valor calculado. **P-09 resuelto:** una celda con fórmula nunca se evalúa y la fila que la contiene es un error de fila ("celda con fórmula"), en columna obligatoria u opcional.
- **Fecha y hora de incidencia (P-09 resuelto):** se acepta una celda nativa de fecha/fecha-hora de Excel o un texto exactamente `YYYY-MM-DD` o `YYYY-MM-DD HH:MM`. Cualquier otro texto es error de fila. La hora, si existe, se interpreta como hora local de Europe/Madrid y se conserva con precisión de minutos; si no existe, solo se guarda la fecha, sin `00:00` inventado. Una celda nativa con hora exactamente 00:00 se trata como solo fecha, porque Excel no distingue ambos casos; un texto con `00:00` explícito conserva esa hora. Comparar (RN-02) fecha y hora: presencia o ausencia de hora, o una hora distinta, es una diferencia relevante. Las horas locales inexistentes o ambiguas por cambio horario no son un caso aparte: la hora se conserva tal como viene, como hora local, sin convertirla a un instante (P-09 resuelto).
- **Order ID (P-09 resuelto):** texto alfanumérico, conservado tal cual (sin recortar ni cambiar mayúsculas/minúsculas). Una celda numérica es error de fila ("Order ID debe ser texto"): no se reconstruyen ceros ni dígitos perdidos por Excel.
- Saltos de línea o caracteres especiales en descripción no son errores por sí mismos. Preservar el texto y tratarlo de forma segura al mostrar/exportar.
- Archivo corrupto, protegido o con varias hojas: rechazo de estructura. **P-06 resuelto:** tamaño máximo del archivo, 10 MB; un archivo mayor se rechaza entero con ese motivo. No hay un límite de filas distinto del tamaño. **P-09 resuelto:** se supone un XLSX curado: los encabezados adicionales no reconocidos se ignoran, las filas totalmente vacías se omiten sin error ni cómputo, las columnas obligatorias se comprueban en cada fila y las opcionales se aceptan como vienen según las reglas de lectura anteriores, sin comprobaciones adicionales. No truncar silenciosamente.

## 3. Clasificación excluyente

**RN-01:** la clave definitiva es proveedor + order ID, garantizada por restricción PostgreSQL. No se añade la sucursal ni se reabre esta decisión.

**RN-02:** campos relevantes para comparar la misma clave: fecha de incidencia, sucursal, importe a reclamar, costos de proveedor, total y descripción. Comparar tras la conversión aprobada de sucursal/proveedor; columna opcional ausente y celda opcional vacía representan el mismo valor ausente. Comparar importes por valor decimal, conservando la precisión almacenada y sin redondear.

| Clase | Condición |
|---|---|
| Con error | La fila no supera las validaciones; se informa el motivo |
| En conflicto | Entre filas válidas con la misma clave, o frente a una incidencia existente, difiere algún campo relevante |
| Duplicada | Misma clave y mismos campos relevantes frente a una incidencia existente o repetición idéntica dentro del archivo |
| Nueva | Fila válida sin coincidencia existente y con una sola aparición válida de su clave en el archivo |

Primero se identifican filas inválidas. Entre las válidas, el conflicto prevalece sobre el duplicado cuando existe alguna diferencia en el grupo de la misma clave. Si el archivo repite una clave con datos idénticos, **todas esas apariciones quedan duplicadas y excluidas**; si difieren, todas quedan en conflicto. No se elige una fila arbitrariamente para importarla.

**RN-03:** solo se importan filas nuevas y válidas. Una sucursal ausente está permitida; una proporcionada debe ser conocida. Duplicados, conflictos y errores no crean incidencias ni outbox. **RN-13:** no se excluye por antigüedad de incidencia.

La vista previa contiene cantidades por clase, motivos por fila y ambas versiones en conflictos con datos existentes. Se permite descargar un informe de excluidas y corregir/reimportar; las incidencias ya confirmadas vuelven a clasificarse y no generan otro correo.

## 4. Confirmación, idempotencia y original

La API limita la confirmación al administrador autorizado y al lote correspondiente. Exige lote En revisión (no descartado) y la versión que se ha revisado. El resumen diferencia incidencias a crear, correos a generar, Glovo sin correo, excluidas y destinatario/plantilla autorizados.

Al confirmar, en **una única transacción PostgreSQL**:

1. Obtener el control del lote y comprobar estado y si ya fue confirmado o descartado.
2. Revalidar las condiciones de negocio y comprobar coincidencias contra las incidencias actuales con apoyo de la restricción de unicidad.
3. Insertar solo las incidencias nuevas y válidas. Las coincidencias sobrevenidas se excluyen y se explican en el resultado.
4. Crear exactamente un registro de outbox por incidencia nueva de Uber Eats o Just Eat, en estado Pendiente. Glovo nace Importada (sin correo), sin outbox.
5. Registrar estado confirmado, usuario, fecha, resultado y auditoría de confirmación.

Un fallo revierte todos esos registros; no deja incidencias definitivas parciales ni correos huérfanos. El staging anterior no se confunde con esos datos y puede conservarse si el lote sigue En revisión. Tras una confirmación exitosa se limpia el staging temporal, sin borrar las incidencias, el resultado guardado ni el original confirmado. Una segunda confirmación devuelve el resultado ya guardado, sin depender del staging ni crear nuevas incidencias, outbox o efectos duplicados.

No enviar desde la petición, triggers o callbacks de confirmación. En el cambio 2 los correos quedan pendientes y el envío está deshabilitado.

Antes de confirmar, verificar que el SHA-256 del original coincide con el hash revisado (ADR-14); la subida no permite sobrescribir. Tras la transacción, el worker copia el original al contenedor inmutable `confirmed` con nombre determinista por lote, verifica el hash y registra el enlace verificable; una discrepancia se registra y alerta, y mientras tanto la limpieza no borra el blob de un lote Confirmado. Blob no participa en la transacción PostgreSQL; comprobar conservación y alertar discrepancias de forma independiente. El outbox guarda la versión autorizada de destinatario y plantilla, sin secretos; una edición posterior no cambia los correos ya autorizados.

## 5. Descarte

RF-17: cancelar antes de confirmar, o pulsar el botón Cerrar sesión, descarta los lotes no confirmados **del usuario**. El botón llama a una operación de la API que los descarta y nada más: no cierra la sesión de Easy Auth. Se elimina archivo y staging; no queda contenido del lote descartado. **No existe caducidad automática ni plazo de inactividad**: un lote En revisión permanece así, confirmable, hasta confirmarse o descartarse, también tras un cierre inesperado del navegador. Si la llamada de descarte falla, se informa al usuario y el lote no cambia de estado. **Un solo lote sin confirmar por usuario**, garantizado por una restricción PostgreSQL que resiste peticiones simultáneas; un lote Rechazado no cuenta. Se puede descartar un lote en Subido, Procesando o En revisión, de modo que un procesamiento atascado no bloquea al usuario.

Confirmación y limpieza se coordinan en PostgreSQL para que una operación no elimine datos de la otra. Lote descartado: no confirmable. Lote confirmado: protegido de la limpieza temporal. Si falla el borrado físico, registrar el error y completar la limpieza; no afirmar que se eliminó lo que sigue almacenado. Cadencia y objetivo de limpieza física pendientes P-05.

## 6. Incidencias, resultados y métricas

- Consulta y exportación XLSX con filtros por proveedor, sucursal, estado y fecha. Mostrar Sin sucursal y valores ausentes de forma explícita.
- Historial de estado con actor, fecha, valor anterior/nuevo y motivo cuando corresponda.
- Marcar Glovo Reclamada cuando se reclama por otra vía, con fecha de reclamación. La vía exacta permanece pendiente P-11.
- Registrar Resuelta o Rechazada e importe recuperado explícito, permitiendo parcial. No asumir que Resuelta implica recuperar todo el importe reclamado.
- Permitir corregir resultados manuales con historial, incluso si se habían considerado finales; esto no revierte ni el lote ni correos.
- Distinguir fecha de incidencia, fecha de reclamación y fecha de recuperación. La hora de incidencia solo existe si venía en el origen; nunca se fabrica.
- Separar actividad por correo y manual Glovo. El envío sin error se reflejará en reclamación por correo al incorporar el cambio 3; importar o crear outbox no cuenta como reclamar.
- Mostrar pendientes de resultado y antigüedad. Agregar en PostgreSQL, sin almacén analítico adicional.
- Recuperado y tasa deben basarse en cantidades registradas. Ausente no es cero. Mostrar datos incompletos y no mezclar métricas de prueba y producción.

**P-04 resuelto (administrador, 2026-11-23):**
- **Fecha por defecto:** fecha de reclamación; el usuario puede elegir otra y siempre se le dice cuál se usa.
- **Reclamación:** toda incidencia con fecha de reclamación (reclamada, resuelta o rechazada). **Recuperación:** toda incidencia marcada Resuelta, tenga o no importe registrado.
- **Tasa de recuperación:** recuperaciones ÷ reclamaciones, por número y no por importe, con todas las reclamaciones del periodo en el denominador (también las pendientes y las rechazadas). Con denominador 0 se muestra «No calculable», nunca 0 % ni error. Con la fecha de recuperación elegida no hay reclamaciones definidas para el periodo, así que la tasa también es «No calculable». Se expresa con cuatro decimales.
- **Antigüedad:** días naturales desde la fecha de reclamación hasta hoy (hora de Madrid) de las reclamaciones sin resultado, de la más antigua a la más reciente, sin umbral ni alertas.
- **Importes incompletos:** se suman los importes conocidos y se avisa «Incompleto» con el número de incidencias sin importe; si no hay ninguno conocido, la cifra queda «Sin datos», nunca 0.
- **Importe recuperado:** sin restricciones (cualquier decimal), con correcciones auditadas.

## 7. Alta manual y auditoría

RF-22: formulario con los mismos campos de negocio y obligatoriedad básica del XLSX. Validar y comprobar proveedor + order ID; una clave existente avisa y no crea otra incidencia. Una nueva incidencia requiere revisión y confirmación antes de persistirse. **P-12 resuelto (administrador, 2026-11-23):** un alta manual de Uber Eats o Just Eat **sí genera correo**, en la misma transacción y con el mismo outbox, nunca con un envío directo; solo Glovo se reclama a mano y no genera correo. Sin destinatario autorizado configurado, ese alta se rechaza.

RF-18 (retirado): no hay API ni pantalla para administrar autorizaciones de identidades Google y roles, sucursales y proveedores. El equipo técnico los mantiene con migraciones y configuración, y el backend solo los lee: la allowlist y los roles (el administrador inicial sale de la configuración), el catálogo de sucursales y los proveedores con destinatarios configurables. Hasta definir los reales (P-01) se utiliza solo el destinatario de prueba. Mantener coherencia entre allowlist y permisos aplicados por FastAPI. No crear contraseñas propias ni cuentas Google. Retirar una identidad la deja sin acceso aunque su sesión Google continúe.

RF-19 (solo registro): auditoría de subidas, confirmaciones, envíos futuros, resultados, correcciones y altas manuales. Solo se añaden registros: no existe operación para editarlos ni borrarlos. La aplicación no ofrece consulta de la auditoría; la consulta el equipo técnico sobre la base de datos. El lote confirmado queda enlazado con su original, usuario y fecha. La auditoría mínima de descartes no conserva filas ni archivo.

## 8. Requisitos funcionales y trazabilidad

| ID | Requisito | Criterio de aceptación |
|---|---|---|
| RF-01 | Subida directa XLSX | Progreso y resultado; API autoriza Blob y registra lote |
| RF-02 | Validar estructura | Tres encabezados obligatorios y una hoja; opcionales pueden faltar |
| RF-03 | Preparar sin incidencias definitivas | Solo Blob/staging antes de confirmar |
| RF-04 | Clasificación excluyente | Una clase por fila, motivos y comparaciones |
| RF-05 | Excluir duplicados y conflictos | Ninguno crea incidencia ni correo |
| RF-06 | Excluir errores y claves existentes | Opcionales ausentes permitidos; sucursal proporcionada debe ser conocida |
| RF-07 | Confirmación con resumen | Cantidades, excluidas, destinatario y versión autorizados |
| RF-08 | Atomicidad PostgreSQL | Incidencias, outbox, estado y auditoría juntos o ninguno |
| RF-09 | Idempotencia | Repetir confirmación no añade efectos |
| RF-10 | Comprobar al confirmar | Coincidencias sobrevenidas se excluyen y se informa |
| RF-15 | Métricas y seguimiento | Correo/Glovo separados y recuperación explícita; criterios de P-04 resueltos |
| RF-16 | Consulta y exportación | Filtros respetados y valores opcionales conservados |
| RF-17 | Descarte explícito | Cancelar y el botón Cerrar sesión eliminan temporales; sin caducidad automática |
| RF-18 | Administración (retirado) | Sin API ni pantalla: autorizaciones, roles, sucursales y proveedores los gestiona el equipo técnico y el backend los lee |
| RF-19 | Auditoría y original | Operaciones registradas y original confirmado enlazado; sin consulta desde la aplicación |
| RF-20 | Informe excluidas | XLSX con filas y motivos para corregir y volver a subir |
| RF-21 | Resultados manuales | Parciales y correcciones con historial |
| RF-22 | Alta manual | Misma unicidad y confirmación humana; correo para Uber Eats y Just Eat (P-12 resuelto) |

Se conservan las reglas originales de negocio compatibles, agrupadas así: RN-01 unicidad; RN-02 clasificación; RN-03 elegibilidad; RN-04 correo solo Uber Eats/Just Eat; RN-06 importes; RN-07 confirmación; RN-09 estructura; RN-10 temporalidad; RN-11 aviso de archivo idéntico; RN-13 sin exclusión por antigüedad; RN-15 resultados. Las reglas RN-05, RN-08, RN-12 y RN-14 se concretan en el cambio 3.

## 9. Escenarios y pruebas previstas

| ID | Dado / Cuando | Entonces |
|---|---|---|
| E-01 | XLSX válido con solo los tres encabezados obligatorios | Vista previa; ninguna incidencia definitiva ni outbox antes de confirmar |
| E-02 | Falta un encabezado obligatorio o hay varias hojas | Archivo rechazado con motivo |
| E-03 | Clave existente con campos relevantes iguales | Duplicada y excluida |
| E-04 | Clave existente con datos distintos | Conflicto, ambas versiones visibles y exclusión |
| E-05 | Sucursal ausente y otra proporcionada desconocida | La primera no falla por ausencia; la segunda tiene error |
| E-06 | 80 filas nuevas válidas, 20 Glovo, y confirmación | 80 incidencias y 60 correos pendientes en una transacción; ningún envío |
| E-07 | Doble clic o petición repetida | Mismo resultado confirmado sin registros adicionales |
| E-08 | Fallo a mitad de confirmación | Ninguna incidencia, outbox ni confirmación parcial del lote |
| E-11 | Cancelar o pulsar Cerrar sesión sin confirmar | Archivo y staging eliminados, lote no confirmable |
| E-12 | Marcar recuperación parcial y luego corregirla | Importe explícito e historial; lote y correo sin reversión |
| E-13 | Alta manual con clave existente | Aviso y ninguna incidencia nueva |
| BE-01 | Repeticiones internas idénticas o distintas | Todas excluidas como duplicadas o conflictos según su grupo |
| BE-02 | Otro lote confirma una clave durante la revisión | Se excluye al confirmar; el resto se importa y se informa |
| BE-03 | Dos confirmaciones simultáneas | Unicidad e idempotencia también bajo concurrencia |
| BE-04 | Cierre inesperado del navegador con un lote En revisión | El lote sigue En revisión y confirmable; al volver, el usuario puede retomarlo, confirmarlo o cancelarlo |
| BE-15 | Falla la llamada de descarte al pulsar Cerrar sesión | Se informa del error y el lote sigue En revisión sin cambios |
| BE-16 | El usuario tiene un lote sin confirmar e intenta subir otro, también con dos solicitudes simultáneas | Se rechaza el segundo indicando el lote pendiente; nunca existen dos. Un lote Rechazado no bloquea y un lote en Procesando puede descartarse |
| BE-17 | Importes `-12.5`, `0` y `12.345` como celdas numéricas, y otro importe como texto `12,50 €` | Los tres numéricos se aceptan con signo y precisión conservados; el texto es error de fila |
| BE-18 | El OpenAPI generado por FastAPI difiere del contrato aprobado | La prueba de contrato falla y bloquea la integración |
| BE-05 | Limpieza y confirmación concurrentes | Nunca se borra un original confirmado ni se confirma un lote ya descartado |
| BE-06 | Un importe tiene más de dos decimales y otro está ausente | Precisión conservada y ausencia sin convertir a cero |
| BE-07 | Se edita destinatario o plantilla después de confirmar | El outbox conserva la versión autorizada |
| BE-08 | Usuario fuera de allowlist o rol de consulta intenta mutar | Acceso denegado por FastAPI |
| BE-09 | Se reinicia el worker durante preparación | Trabajo recuperable por su lote persistente sin incidencias definitivas anticipadas |
| BE-10 | Se confirma un lote | La auditoría registra usuario, fecha y enlace al original revisado, verificables en la base de datos |
| BE-11 | Se limpia staging tras confirmar y se repite la confirmación | Incidencias y original conservados; mismo resultado guardado y ningún efecto nuevo |
| BE-12 | Celda nativa con `2026-10-12 20:22`, otra solo con fecha y otro texto `12/10/2026` | La primera guarda fecha y hora Europe/Madrid, la segunda solo fecha sin hora, la tercera es error de fila |
| BE-13 | Misma clave con y sin hora, o con horas distintas, frente a una incidencia existente | Conflicto por diferencia en la fecha/hora de incidencia |
| BE-14 | Order ID `AB-1029x` como texto y otro como celda numérica | El primero se conserva tal cual; el segundo es error de fila |

TDD obligatorio para clasificación/deduplicación y confirmación. Integración con PostgreSQL real para unicidad, transacciones y concurrencia, y con Azurite real para archivos. Archivos sintéticos y muestra anonimizada para parser/importes. Pruebas de integración de la UI aprobada con la API real. Prueba de contrato: el OpenAPI que genera FastAPI debe coincidir con `docs/api/openapi.yaml` aprobado; un cambio incompatible falla la prueba hasta que se apruebe una nueva versión. RNF aplicables: 01, 03–11 y 13–16; RNF-02 se prepara con outbox y se completa en el cambio 3.

## 10. Definición de hecho y pendientes

Frontend conectado al backend, flujo de revisión/confirmación verificable, original conservado, auditoría activa y outbox pendiente sin envíos. Modelo migrable y reglas cubiertas por las pruebas del cambio. Resolver antes de implementar su comportamiento los pendientes P-04, P-10 y P-12 (P-06 y P-09 están resueltos); conservar los restantes visibles en la visión general. Incorporar P-08 antes de usar datos reales para evitar reclamar de nuevo lo ya gestionado manualmente.

## 11. Fases de implementación

`tasks.md` se divide en estas fases, en este orden. Cada una termina con sus pruebas en verde y una revisión antes de empezar la siguiente. Se mantiene un solo cambio `backend`.

| Fase | Contenido | Verificación mínima |
|---|---|---|
| 1 | Modelo de datos, migraciones reversibles, permisos y auditoría; catálogo inicial de sucursales y proveedores por configuración | Migraciones arriba/abajo; permisos por rol (BE-08); auditoría activa |
| 2 | Importación y clasificación (TDD): lectura XLSX, reglas de fila, staging, vista previa | E-01 a E-05, BE-01, BE-06, BE-09, BE-12 a BE-14, BE-17 |
| 3 | Confirmación atómica e idempotente y outbox sin envío | E-06 a E-08, BE-02, BE-03, BE-07, BE-10, BE-11 |
| 4 | Descarte, Cerrar sesión, lote único por usuario y limpieza | E-11, BE-04, BE-05, BE-15, BE-16 |
| 5 | Incidencias, exportación, resultados y alta manual | E-12, E-13, RF-16, RF-21, RF-22 |
| 6 | Métricas y panel (P-04 resuelto) | RF-15 |
| 7 | Integración del frontend aprobado con la API real | Recorridos UI-01 a UI-12 contra la API real |

El catálogo inicial de sucursales debe existir antes de la fase 2. La fase 2 requiere además P-06 y P-09 resueltos en lo que le afecta, y las fases 2 a 7 requieren la aprobación explícita del cambio 1 (la fase 1 no implementa lógica de negocio).
