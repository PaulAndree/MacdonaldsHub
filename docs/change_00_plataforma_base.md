# Cambio 0 · platform-base

> Fuente para el futuro cambio OpenSpec `platform-base`. Contexto en [project_overview.md](project_overview.md) y [architecture.md](architecture.md).
> Dependencias: ninguna. Siguiente entrega: [frontend](change_01_frontend.md).

## 1. Objetivo

Disponer de una base desplegable y verificable antes de diseñar e implementar los flujos de negocio. Este cambio entrega infraestructura y procesos mínimos; no implementa importación, panel ni envío.

## 2. Alcance

- Estructura separada de frontend React + TypeScript y backend Python. El backend comparte código e imagen entre API FastAPI y worker.
- Bicep para Container Apps, registro de imágenes, PostgreSQL Flexible Server (uno por entorno, creado por Bicep, ADR-15), Blob con contenedores `uploads` y `confirmed` (ADR-14), Key Vault con identidad administrada, observabilidad y conectividad.
- Tres servicios de aplicación: frontend mínimo, API mínima y **un worker** con réplica permanente, sin ingress público y con exclusión mutua PostgreSQL frente a solapamientos.
- Contenedores, comprobaciones de salud y configuración por variables de entorno. No se crean servicios distintos para importar y enviar.
- Compose reproducible con frontend, API, worker, PostgreSQL persistente, Azurite persistente y captura SMTP local. Un comando arranca el entorno; no requiere acceso a Azure para pruebas locales.
- `.env.example` sin secretos y `.env` excluido del versionado. Gestor de secretos e identidad administrada para servicios Azure.
- Login **Google + Easy Auth de Container Apps** (ADR-12): Easy Auth solo en el frontend, que reenvía `/api` a una API con ingress interno; middleware de autorización FastAPI basado en allowlist sobre la identidad reenviada. Administrador inicial configurado fuera del código; comprobar permisos por rol.
- Adaptador explícito de identidad para desarrollo local, con rol configurable. Debe ser imposible habilitarlo en Azure: el proceso rechaza el arranque si está activo fuera de local.
- Interfaz `StorageService`, Azurite por configuración local y Blob con identidad administrada en Azure. Permiso temporal de subida directa desde navegador, con CORS en ambos entornos y acceso limitado al archivo autorizado.
- OpenTelemetry para API y worker, destino Azure Monitor/Application Insights; salida local configurable.
- GitHub Actions para lint, pruebas, construcción de imágenes y despliegue. Migraciones versionadas; herramienta propuesta Alembic.
- Entorno de prueba separado de producción, con base de datos, almacenamiento y configuración de correo propios. No se copian lotes de prueba a producción.
- Flujo técnico mínimo: usuario autorizado → pantalla mínima → API → PostgreSQL, y subida de archivo técnico a Blob/Azurite.

## 3. Fronteras

La pantalla y API mínimas verifican identidad y conectividad; no anticipan el diseño funcional del cambio 1 ni la lógica del cambio 2. El worker solo arranca y demuestra su ciclo de vida/exclusión: la importación se incorpora en el cambio 2 y el envío en el 3.

Este cambio prepara la persistencia y el mecanismo de migraciones, sin diseñar todo el modelo de negocio. La autorización y las trazas se aplican desde el inicio. Las identidades administradas de los servicios Azure no cambian el login Google del usuario.

## 4. Requisitos y aceptación

| ID | Aplicación al cambio | Criterio |
|---|---|---|
| RNF-03 | Persistencia ante reinicios | Reiniciar contenedores no elimina datos de PostgreSQL ni archivos del almacenamiento |
| RNF-04 | Identidad y secretos | Google autentica, FastAPI comprueba allowlist y permisos; secretos fuera del código |
| RNF-05 | Trazas | Peticiones y procesos identifican actor, correlación y resultado sin datos secretos |
| RNF-09 | Procesos separados | API y worker comparten backend; solo un worker activo procesa trabajo |
| RNF-10 | Operabilidad | Logs, alertas técnicas y una restauración de prueba documentada |
| RNF-11 | Azure | Servicios desplegados en Container Apps con PostgreSQL externo |
| RNF-13 | Tiempo | Eventos con criterio UTC y presentación Europe/Madrid; la hora de la incidencia es opcional y nunca se inventa |
| RNF-14 | Local reproducible | Compose levanta los servicios y permite verificar almacenamiento y base de datos reales |
| RNF-15 | Configuración | Mismas reglas y código, interfaces/adaptadores seleccionados por variables |
| RNF-16 | Identidad de desarrollo restringida | Arranque en Azure rechazado si está activa |

## 5. Escenarios

| ID | Dado / Cuando | Entonces |
|---|---|---|
| BASE-01 | Usuario sin sesión accede a la aplicación | Se inicia autenticación con Google mediante Easy Auth |
| BASE-02 | Usuario autenticado fuera de la allowlist llama a FastAPI | Acceso denegado, aunque Google haya autenticado correctamente |
| BASE-03 | Administrador inicial autorizado accede | Puede completar el flujo técnico pantalla → API → PostgreSQL |
| BASE-04 | Una petición intenta falsificar identidad mediante cabeceras | No obtiene acceso fuera del mecanismo confiable de Easy Auth |
| BASE-05 | Se arranca Compose y se sube un archivo técnico | Está en Azurite y la API lo identifica; no se crea una incidencia |
| BASE-06 | Reinician PostgreSQL, Azurite y procesos de aplicación | Se conservan los datos y los servicios se recuperan |
| BASE-07 | Se superponen dos revisiones del worker | La exclusión PostgreSQL impide procesar simultáneamente el mismo trabajo |
| BASE-08 | Identidad de desarrollo habilitada en Azure | La aplicación rechaza arrancar con error claro |
| BASE-09 | Se verifica captura SMTP local | Ningún correo se dirige a proveedores reales; no requiere implementar el consumidor de outbox |
| BASE-10 | Se despliega en pruebas y se comprueban recursos | Base de datos y almacenamiento están aislados de producción |
| BASE-11 | Se intenta llamar a la API directamente desde fuera del entorno de Container Apps, con o sin cabecera de identidad | No es accesible (ingress interno) |
| BASE-12 | La API recibe una petición sin cabecera de identidad de Easy Auth en Azure | Responde 401 antes de consultar la allowlist |

## 6. Definición de hecho

CI verde, imágenes construibles, despliegue técnico verificado, conectividad local y Azure comprobadas, restauración documentada y secretos protegidos. Pruebas de integración contra PostgreSQL y Azurite reales; no presentar el esqueleto como funcionalidad de negocio terminada.

Pendientes aplicables: P-05 (objetivos de operación), P-07 (identidades y allowlist) y configuración concreta de los entornos. Los valores pendientes se resuelven antes de implementar su parte; no se publican credenciales en documentación.
