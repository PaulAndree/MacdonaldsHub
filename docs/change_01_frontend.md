# Cambio 1 · frontend

> Fuente para el futuro cambio OpenSpec `frontend`. Contexto en [project_overview.md](project_overview.md) y [architecture.md](architecture.md).
> Depende de [platform-base](change_00_plataforma_base.md). La integración real corresponde a [backend](change_02_backend.md).

## 1. Objetivo y cierre del cambio

Permitir al administrador **ver, recorrer y aprobar el diseño y la lógica de interacción antes de implementar la lógica de negocio**. Entregar una SPA navegable con datos de ejemplo coherentes con los requisitos definitivos.

El cambio no se considera cerrado solo porque haya pantallas construidas. Requiere aprobación explícita del administrador del layout, navegación, flujos, mensajes y acciones. Se registra qué versión del diseño y contrato se ha aprobado.

## 2. Alcance de interfaz

| Área | Pantallas e interacciones | Trazabilidad |
|---|---|---|
| Acceso | Login Google, acceso denegado por allowlist, sesión y permisos visibles | RNF-04, RNF-16 |
| Importación | Selección XLSX, progreso de subida, procesamiento, rechazo de estructura y aviso de archivo idéntico | RF-01, RF-02, RF-03 |
| Vista previa | Resumen y detalle de nuevas, duplicadas, conflictos y errores; versiones comparadas y motivos; informe descargable | RF-04, RF-05, RF-06, RF-20 |
| Confirmación | Resumen de incidencias y correos, destino de prueba y plantilla revisada, acción única, doble clic, resultado real | RF-07, RF-08, RF-09, RF-10 |
| Cancelación y descarte | Cancelar antes de confirmar, botón Cerrar sesión que descarta los lotes no confirmados, lote descartado no confirmable y aviso de lote En revisión pendiente al volver a entrar | RF-17 |
| Incidencias | Listado, detalle, filtros, exportación, historial y estados | RF-16, RF-21 |
| Resultados | Marcar reclamación manual Glovo, recuperación parcial, rechazo y corrección auditada | RF-21 |
| Panel | Correo y Glovo diferenciados, fechas diferenciadas, recuperado explícito, pendientes y antigüedad | RF-15 |
| Alta manual | Formulario, aviso de duplicado/conflicto, revisión y confirmación antes de guardar | RF-22 |
| Correo | Pendientes, Enviando, Enviado y Error; pausa/reanudación, motivos y totales | RF-11, RF-12, RF-13, RF-14 |

## 3. Reglas de interacción

- Interfaz en español, navegador de escritorio, navegación por teclado, contraste y mensajes comprensibles.
- No mostrar incidencias definitivas ni correos como creados antes de confirmar. Distinguir explícitamente la preparación temporal.
- Reflejar tres encabezados obligatorios y cinco columnas opcionales. Aceptar ausencia de sucursal e importe en los ejemplos. Mostrar importe desconocido y Sin sucursal, sin rellenarlos con cero o valores inventados.
- Mostrar la fecha de incidencia como `YYYY-MM-DD` y, solo si existe, la hora `HH:MM` (Europe/Madrid); sin hora no se muestra `00:00`. Los importes no se fuerzan a dos decimales.
- El backend es la autoridad de validación y deduplicación. La clasificación de ejemplo no se convierte en lógica de negocio duplicada en el navegador.
- Confirmar explica que no hay deshacer ni cancelación posterior. Deshabilitar dobles acciones mientras se espera respuesta; un fallo de red no se presenta como certeza de que la confirmación no ocurrió.
- Cancelar está disponible solo antes de confirmar. Cerrar sesión pide confirmación si hay un lote sin confirmar, indica que se descartará, solo descarta lotes y no cierra la sesión de Google. No hay caducidad: al volver a entrar, un lote En revisión pendiente se muestra para retomarlo, confirmarlo o cancelarlo. Con un lote sin confirmar, la subida de otro archivo está deshabilitada y explica el motivo.
- Los ejemplos de correo reflejan un intento por registro y un mínimo de 30 s entre inicios. No hay botones de reintento, reenvío o cancelación posterior.
- Pausar impide nuevos intentos; la interfaz avisa que uno ya iniciado puede terminar.
- El entorno de prueba se identifica de forma visible. Sus destinatarios y métricas no se presentan como actividad real de producción.
- Permisos visibles coherentes con la matriz de arquitectura. Ocultar acciones no sustituye a la autorización real que implementará FastAPI.
- Mostrar sin datos, cargando, error, datos incompletos, permiso denegado, lote descartado y cola pausada, además del recorrido exitoso.
- Los criterios de métricas todavía pendientes se identifican como ejemplos de diseño, sin presentarlos como fórmulas aprobadas.

## 4. Contrato frontend/backend

Antes del cierre se acuerda el contrato de operaciones que necesita la UI, con entradas, salidas, estados y errores. En este cambio se documenta y se utiliza con ejemplos; el cambio 2 implementará la API real. No es necesario incorporar un servidor de negocio adicional para servir ejemplos.

El contrato es un **archivo OpenAPI versionado en `docs/api/openapi.yaml`**. Los datos de ejemplo del frontend se sirven con mocks generados a partir de él, y la aprobación del administrador registra la versión exacta del contrato aprobada junto con la del diseño. Los cambios posteriores al contrato aprobado requieren nueva aprobación.

| Operación | Información necesaria |
|---|---|
| Sesión y permisos | Identidad autorizada, rol y entorno; estados no autenticado / no autorizado |
| Preparar subida y solicitar procesamiento | Identificador de lote, acceso temporal Blob y estado del archivo |
| Consultar y revisar lote | Clases, filas, motivos, comparación, resumen, estado del lote y versión revisada |
| Confirmar o descartar | Identificador y versión revisada; resultado confirmado o rechazo por estado (p. ej. lote descartado) |
| Consultar incidencias y exportar | Filtros, datos, estados, fechas, importes opcionales e historial |
| Alta manual y resultados | Datos, duplicado/conflicto, resumen de confirmación, importe recuperado y correcciones |
| Consultar métricas | Cifras por canal/proveedor/sucursal y criterios de fecha explícitos; datos incompletos |
| Consultar cola y controlar pausa | Estados, motivo de error, intervalo y pausa global; sin reintento |

El contrato distingue fecha de incidencia de marcas temporales del sistema y valores ausentes de cero. No se fijan fórmulas ni detalles abiertos como si estuvieran aprobados.

## 5. Escenarios de revisión

| ID | Dado / Cuando | Entonces |
|---|---|---|
| UI-01 | Se recorre un XLSX de ejemplo con solo los tres encabezados obligatorios | Se muestra vista previa válida con opcionales ausentes |
| UI-02 | Se revisa un ejemplo con nuevas, duplicadas, conflictos y errores | Se entiende qué se importará y por qué se excluye cada fila |
| UI-03 | Se confirma la vista de ejemplo | Se distingue preparación de incidencias definitivas y correos pendientes |
| UI-04 | Se cancela el lote de ejemplo o se pulsa Cerrar sesión con un lote sin confirmar | La vista ya no permite confirmarlo |
| UI-05 | Se registra una recuperación parcial y se corrige un marcado | Se muestran importe explícito y el historial de la corrección |
| UI-06 | Se consulta el panel de prueba | Identifica entorno, correo/Glovo y fechas; no inventa valores faltantes |
| UI-07 | Un envío de ejemplo termina en Error | Se muestra el motivo y no existe acción de reintentar |
| UI-08 | Se pausa la cola con un envío iniciado | Se explica que puede terminar y no se inician otros |
| UI-09 | Se recorre un alta manual duplicada y otra nueva | La primera se rechaza; la nueva requiere confirmación antes de figurar guardada |
| UI-10 | Usuario de consulta intenta una acción administrativa | El recorrido representa acceso denegado |
| UI-11 | El administrador revisa todos los recorridos | Aprueba layout, navegación y lógica de interacción o solicita ajustes antes del cierre |
| UI-12 | Hay un lote sin confirmar y se intenta subir otro archivo | La subida está bloqueada, se indica el lote pendiente y se ofrece retomarlo o cancelarlo |

## 6. Fuera de alcance y entrega

Fuera de alcance: pantallas de administración de autorizaciones, roles, sucursales y proveedores, consulta de auditoría y pantalla técnica de diagnóstico (el administrador es el de la franquicia, no el técnico: esas tareas las hace el equipo técnico y no tienen interfaz), parser XLSX real, deduplicación real, migraciones de negocio, persistencia de incidencias, outbox real y envío. La autenticación técnica mínima procede del cambio 0. El cambio 2 reemplaza los ejemplos por integración real preservando los recorridos aprobados.

Entregar frontend navegable, estados de ejemplo, contrato documentado y aprobación del administrador. RNF aplicables: 04, 07, 08, 13 y 15. Los RF de la tabla se validan aquí en interfaz; su comportamiento real pertenece a los cambios 2 y 3.
