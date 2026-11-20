# Delivery Hub · Visión general del proyecto

> Fuente de requisitos: decisiones aprobadas por el administrador y recogidas en estos documentos. Sustituyen las reglas anteriores incompatibles.
> **[Por definir]**, **[por confirmar]** y **[pendiente]** identifican decisiones abiertas; no autorizan a inventar requisitos.

## 1. Objetivo y proceso actual

Delivery Hub centraliza las incidencias de delivery de una franquicia de McDonald's frente a Uber Eats, Just Eat y Glovo. Busca reducir trabajo manual, recuperar importes reclamables y facilitar el seguimiento.

El administrador consulta los portales, prepara un Excel unificado, envía una reclamación por incidencia a Uber Eats y Just Eat y revisa las respuestas. Glovo se reclama por otra vía. No se dispone de API de los portales para recopilar incidencias.

## 2. Flujo obligatorio

1. El administrador sube el XLSX desde el frontend directamente a Azure Blob Storage mediante un permiso temporal concedido por la API.
2. El backend, mediante la tarea de importación del único worker, lee y valida el archivo. Detecta repeticiones dentro del Excel y compara las filas con PostgreSQL usando **proveedor + order ID**. Guarda la preparación en tablas de **staging**.
3. El frontend muestra la vista previa preparada por el backend: nuevas, duplicadas, en conflicto o con error. **Todavía no existen incidencias definitivas ni correos pendientes de ese lote.**
4. El administrador confirma. El backend vuelve a comprobar duplicados y, en **una única transacción PostgreSQL**, crea las incidencias nuevas y válidas, el outbox correspondiente, el estado confirmado del lote y la auditoría de confirmación.
5. El worker consulta el outbox y realiza un intento por correo, uno por uno, con **al menos 30 segundos entre el inicio de dos intentos consecutivos**. Solo Uber Eats y Just Eat generan correo. Glovo se importa sin correo.
6. El administrador registra resultados e importes recuperados, incluidos los parciales. El panel muestra el seguimiento y las métricas del entorno correspondiente.

```text
XLSX -> Blob -> backend / staging PostgreSQL -> vista previa
                                                  |
                                             Confirmar
                                                  |
                                                  v
                      PostgreSQL: incidencias + outbox + auditoria
                                                  |
                                                  v
                                     Worker -> correo, cada 30 s
```

La transformación y validación para la vista previa ocurren antes de confirmar. La confirmación convierte filas válidas en incidencias definitivas. El XLSX original permanece en Blob; PostgreSQL guarda sus datos estructurados. **El outbox es una tabla de PostgreSQL, sin otro servicio de colas.**

## 3. Usuarios y acceso

Recorrido único: **usuario → login con Google → Easy Auth de Azure Container Apps → middleware de autorización FastAPI → allowlist**. La identidad debe estar autenticada y autorizada.

| Rol | Funciones |
|---|---|
| Administrador | Subir, revisar, cancelar antes de confirmar, confirmar, consultar, registrar resultados, alta manual y administración. Existe un administrador inicial autorizado. |
| Gerente global | Consulta de incidencias y panel; habilitación de este usuario secundario [por confirmar]. |

La aplicación administra autorizaciones y roles, no contraseñas ni cuentas de Google. La matriz de permisos está en [architecture.md](architecture.md).

## 4. Contrato de entrada XLSX

Existen **ocho encabezados reconocidos; solo tres son obligatorios**. Las cinco columnas opcionales pueden faltar completamente y admitir celdas vacías.

| Encabezado | Encabezado obligatorio | Valor obligatorio por fila |
|---|---|---|
| Fecha y hora | Sí | Sí: fecha con hora opcional, `YYYY-MM-DD` o `YYYY-MM-DD HH:MM` (por ejemplo `2026-10-12 20:22`), hora local de Europe/Madrid; la hora no es obligatoria ni se inventa |
| Sucursal | No | No |
| Order ID | Sí | Sí: texto alfanumérico, conservado tal cual; una celda numérica es error de fila |
| Proveedor | Sí | Sí: Uber Eats, Just Eat o Glovo |
| Importe a reclamar | No | No: si existe, número con el signo del origen (sin validar signo) |
| Costos de proveedor | No | No: si existe, número con el signo del origen |
| Total | No | No: si existe, número con el signo del origen |
| Descripción | No | No |

- Una sola hoja. Volumen habitual: 300–600 filas. Tamaño y número máximos [por definir], sin truncado silencioso.
- Moneda euro y precisión decimal conservada del XLSX, sin redondeo obligatorio a dos decimales. Un importe ausente es desconocido, no cero.
- Solo se convierten a minúsculas los valores de sucursal y proveedor. No se recortan espacios, crean alias, corrigen identificadores ni aplican otras normalizaciones en v1.
- Una sucursal ausente no invalida la fila. Si se proporciona, debe corresponder a una sucursal conocida tras la conversión a minúsculas.
- No se ejecutan macros ni se evalúan fórmulas. Las representaciones de celdas todavía no acordadas se mantienen pendientes.
- La clave **proveedor + order ID** identifica inequívocamente una incidencia. La sucursal no participa en la clave y esta decisión no se reabre.

## 5. Clasificación y confirmación

| Clase | Significado | Resultado al confirmar |
|---|---|---|
| Nueva | Clave inexistente y fila válida, sin repetición excluyente en el archivo | Crear incidencia y, para Uber Eats o Just Eat, outbox |
| Duplicada | Misma clave y mismos campos relevantes | Excluir |
| En conflicto | Misma clave y diferencias en campos relevantes | Excluir |
| Con error | Incumple el contrato de fila | Excluir; los errores de estructura rechazan el archivo entero |

La vista previa muestra motivos, cantidades, destino autorizado y resumen de incidencias a importar y correos a generar. Confirmar es idempotente: doble clic o repetición de petición no crea más registros. Las coincidencias surgidas entre revisión y confirmación se excluyen y se informa del resultado real. El [cambio 2](change_02_backend.md) precisa la comparación de campos.

## 6. Temporalidad y conservación

- Antes de confirmar, Blob y staging contienen datos temporales, no incidencias definitivas.
- **Cancelar** o pulsar el botón **Cerrar sesión** de la aplicación descarta los lotes no confirmados del usuario y elimina archivo y staging. Ese botón solo descarta lotes: no cierra la sesión de Google/Easy Auth.
- Cada usuario puede tener **un único lote sin confirmar** a la vez; para subir otro hay que confirmar o descartar el actual.
- **No hay caducidad automática.** Un lote sin confirmar permanece En revisión hasta que se confirma, se cancela o se pulsa Cerrar sesión; tras un cierre inesperado del navegador o de la sesión, el usuario puede retomarlo.
- La limpieza se coordina con la confirmación para no borrar un lote que se está confirmando. Un lote descartado no puede confirmarse.
- Al confirmar se conserva el XLSX original en Blob, enlazado a lote, usuario y fecha. Su conservación se verifica fuera de la transacción PostgreSQL. Retención del original confirmado [por definir].
- Tras una confirmación exitosa se limpia el staging temporal, conservando las incidencias definitivas, el resultado de confirmación y el original confirmado.
- Tras confirmar no se deshace el lote ni se cancelan correos. Una corrección auditada de un resultado manual no revierte la importación ni el envío.

## 7. Envío y entorno de prueba

El worker realiza **un solo intento por correo**, sin reintentos automáticos ni reenvíos manuales en v1. Registra **Enviado** si la operación termina sin error y **Error** si falla o su resultado no es verificable. Enviado no acredita entrega final. Pausar impide nuevos intentos, sin cancelar uno ya iniciado.

Los destinatarios reales todavía no se conocen. Solo se utiliza **un destinatario de prueba configurado**, en un **entorno separado de producción**, con base de datos, almacenamiento y métricas propios. No se pasan lotes ni outbox de prueba a producción; los datos reales se importan allí de forma independiente.

Las pruebas pueden recorrer todos los estados, pero sus envíos y recuperaciones no cuentan en las métricas reales. Plantilla única más order ID; asunto y cuerpo [pendientes]. Remitente: buzón institucional proporcionado; método de acceso y configuración operativa [por confirmar].

## 8. Seguimiento y métricas

- Separar reclamaciones reales por correo y reclamaciones manuales de Glovo.
- Registrar importe recuperado explícito y permitir recuperación parcial, sin inferirlo de Resuelta.
- Diferenciar fecha de incidencia, reclamación y recuperación. La fecha de incidencia no exige hora; los eventos del sistema sí tienen marca temporal.
- Consultar y exportar con filtros por proveedor, sucursal, estado y fecha; mostrar historial.
- Mostrar reclamaciones sin resultado y su antigüedad. Permitir rectificar resultados previamente marcados dejando historial.
- No convertir importes ausentes en cero ni presentar sumas incompletas sin advertencia. Mostrar las incidencias sin sucursal como Sin sucursal.

| KPI | Definición de negocio |
|---|---|
| Importe reclamado | Importe de reclamaciones registradas como realizadas, separando correo y Glovo; no solo importadas ni con envío erróneo |
| Importe recuperado | Importe explícito registrado como recuperado |
| Tasa de recuperación | Importe recuperado / importe reclamado, con población y periodo coherentes |
| Envíos duplicados | Seguimiento de correos repetidos por incidencia; objetivo operativo 0 |
| Tiempo por reclamación | Observación del trabajo del administrador |

Fecha por defecto de filtros, fórmula temporal de tasa, criterio de antigüedad y agregaciones con importes incompletos **[por definir antes de implementar métricas]**. No se mezclarán periodos o poblaciones implícitamente. Objetivos numéricos [por definir].

## 9. Alcance v1

Incluye importación, vista previa, confirmación idempotente, deduplicación, outbox, envío espaciado sin reintentos, resultados manuales, recuperación parcial, alta manual, administración, auditoría y backups. El alta manual comparte validación, deduplicación y confirmación; no crea correos sin aprobación humana.

Fuera de alcance: correo para Glovo, cancelación posterior a confirmar, reintentos o reenvíos de correo, lectura automática de respuestas, recopilación desde portales, conciliación con liquidaciones, evidencias adjuntas y segunda interfaz. Se mantiene la regla de no excluir incidencias por antigüedad.

## 10. Cuatro cambios y orden de entrega

| # | Cambio | Fuente | Resultado verificable |
|---|---|---|---|
| 0 | `platform-base` | [change_00_plataforma_base.md](change_00_plataforma_base.md) | Entorno desplegable, identidad y conectividad; API y worker mínimos |
| 1 | `frontend` | [change_01_frontend.md](change_01_frontend.md) | Diseño y flujos navegables con ejemplos, aprobados por el administrador |
| 2 | `backend` | [change_02_backend.md](change_02_backend.md) | Frontend integrado, datos persistentes y confirmación con outbox; todavía sin envíos |
| 3 | `email-sending` | [change_03_envio_correos.md](change_03_envio_correos.md) | Flujo completo de envío y seguimiento en entorno de prueba |

Son las únicas cuatro fuentes de cambios. El frontend se aprueba antes de implementar la lógica de negocio. La arquitectura está en [architecture.md](architecture.md). La documentación prevista no representa funcionalidad implementada; los futuros artefactos formales se gestionan en OpenSpec.

## 11. Decisiones pendientes

| ID | Decisión |
|---|---|
| P-01 | Dirección del destinatario de prueba y direcciones reales de Uber Eats y Just Eat |
| P-02 | Acceso y configuración operativa del buzón; nunca publicar credenciales |
| P-03 | Asunto y texto de plantilla; inclusión de descripción libre; el correo solo incluye el número de incidencia (sin importes ni descripción) |
| P-04 | Fórmulas temporales, filtros, antigüedad y tratamiento de importes incompletos |
| P-05 | Retención de originales confirmados, objetivos de disponibilidad, backup/restauración y cadencia de limpieza |
| P-06 | Límites máximos XLSX y muestra anonimizada de entrada |
| P-07 | Habilitación del gerente global, valores e identificador estable de la allowlist |
| P-08 | Incorporación del histórico de reclamaciones manuales antes de usar datos reales |
| P-09 | Celdas fórmula, encabezados adicionales, filas vacías y horas locales inexistentes o ambiguas por cambio horario, sin ampliar las normalizaciones aprobadas. Resueltos: fecha/hora y Order ID (ver cambio 2) |
| P-10 | Si debe existir relación matemática entre Total, Importe a reclamar y Costos de proveedor |
| P-11 | Vía externa de reclamación Glovo, protección de datos libres y obligaciones adicionales |
| P-12 | Si el alta manual genera correo; siempre requiere confirmación antes de crear la incidencia |

Estos puntos no reabren unicidad, flujo, identidad, cuatro cambios, ausencia de caducidad automática ni prohibición de reintentar correos.
