# PROTOCOLO OPERATIVO — Integración ACLIMAR Assistant
**Versión:** 1.0 | **Fecha:** 09/10/2026 | **Estado:** para entregar a Aider | **Modo inicial:** AUDITORÍA SIN IMPLEMENTACIÓN

## 0. Orden maestra para Aider (leer antes de cualquier operación)
Actúa como **auditor técnico, arquitecto de integración y coordinador de implementación**. Debes analizar exhaustivamente DOS aplicaciones locales existentes, **SIN MODIFICARLAS**, y diseñar una tercera aplicación con la mejor UI de AI Studio y el backend funcional verificado del proyecto Codex. La aplicación final se construirá en un tercer directorio bajo control de Git/GitHub. Tu primer entregable será **únicamente un informe de auditoría y un plan de trabajo**, sin implementar funcionalidades. Espera la aprobación humana `APROBADO PLAN` antes de empezar la ejecución.

### Directorios — regla de protección máxima
- `SOURCE_UI = C:\Users\a4863\asistente-comercial-AIStudio` — **SOLO LECTURA**.
- `SOURCE_CORE = C:\Users\a4863\asistente-comercial-aclimar` — **SOLO LECTURA**.
- `TARGET = C:\Users\a4863\asistente-comercial-gemini` — **único directorio de trabajo autorizado**, previa inspección de si existe y de su contenido.
- **PROHIBIDO** en los directorios SOURCE: guardar/editar/eliminar/copiar encima, ejecutar migraciones, instalar dependencias, crear cachés, ejecutar comandos que creen artefactos, cambiar ramas, hacer checkout, commit, reset, clean, stash, fetch, pull, push o modificar configuraciones Git. No ejecutar sus aplicaciones apuntando a sus bases reales para probarlas. Evitar incluso herramientas de análisis que escriban `__pycache__`, logs o temporales en esos directorios. Inspeccionarlos mediante lecturas de archivos y metadatos, o mediante **copias de trabajo hacia TARGET** cuando se necesiten pruebas dinámicas.
- **No asumir que TARGET está vacío**: si tiene contenido, inventariar antes de tocarlo y solicitar decisión sobre conservación/uso; no borrarlo automáticamente.
- No modificar la base SQLite productiva ni credenciales originales. Prohibido copiar `crm.db`, bases de datos reales, `.env`, archivos de claves, tokens, Keyring, mensajes privados, perfiles de navegador o secretos a TARGET, Git o servicios cloud.
- GitHub no debe recibir correos reales, datos personales de clientes, documentos comerciales, secretos ni ficheros SQLite con datos. Utilizar fixtures sintéticos.

## 1. Entradas y jerarquía de autoridad
**Entradas documentalmente disponibles:**
1. `MF_Lovable_ACLIMAR_Assistant.md.markdown`: contrato funcional histórico; exige local-only, FastAPI/Python/SQLite, API CRM, revisiones y aprobaciones, IMAP, Calendar, borradores sin SMTP, controles CSRF/Origin/Host, Keyring y auditoría.
2. `AIStudio_creacion_asistente.txt`: autodescripción de la aplicación generada en AI Studio; **no constituye evidencia de implementación**.
3. Los archivos, historial Git, tests y estado real de los dos directorios inspeccionados en modo solo lectura.

**Orden para resolver discrepancias:** (a) restricciones expresas de este protocolo; (b) evidencia del código, tests reproducibles y esquema/migraciones del proyecto Codex; (c) decisiones humanas aprobadas en el nuevo repositorio; (d) MF como objetivos y restricciones; (e) descripciones promocionales de AI Studio como hipótesis por verificar. Ante contradicción material: registrar ADR, detener ese bloque y elevar una pregunta concreta, con recomendación y opciones.

**Advertencia de obsolescencia:** el MF declara migraciones hasta `0011`, pendiente fase `6N-E` y baseline `5c50acf...`. El progreso posterior comunicado registra la fase `6O` aceptada, commit `8196a2ed4d4adcdfa1c263854d0b3059459ea6f5`, 1512 tests pasados y 2 omitidos, además de 172 focales; la ejecución MOVE por UI y reconciliación real estaban deshabilitadas. **Ambos son referencias históricas, no hechos que debas asumir del checkout actual**. Obtener HEAD, árbol de migraciones, suite y capacidades reales mediante inspección. No degradar ni reimplementar componentes que ya funcionen.

## 2. Resultado perseguido y límites
Construir una aplicación Windows, local de un usuario, con frontend visual moderno basado en las **pantallas y componentes efectivamente encontrados** en AI Studio; backend autoritativo FastAPI/Python/SQLite y lógica auditada procedente de Codex; APIs REST/JSON solo si se justifica una separación frontend/backend. No está autorizado sustituir backend por servicios cloud, Supabase/Firebase, ni implantar login público/multiusuario. Solo bind `127.0.0.1` (validación backend real, no solo configuración UI).

Áreas funcionales a inventariar: Dashboard, correo y conversaciones, análisis IA, revisión humana, tareas, siguientes pasos, Google Calendar, borradores, notas, WhatsApp manual, CRM por API, auditoría, configuración y **archivado/movimiento de correo** si existe en el backend actual. Clasificar cada función como `probada`, `implementada no probada`, `solo maqueta`, `ausente`, o `bloqueada intencionalmente`. Una pantalla con mocks no cuenta como funcional. **No implementar todas las áreas por anticipado:** priorizar paridad y migración gradual.

Invariantes de seguridad innegociables:
- IA propone; humanos aprueban. La aprobación del contenido y la ejecución externa son actos diferentes.
- **Sin envío SMTP desde la aplicación**, sin botón de envío y sin rutas equivalentes; el usuario envía manualmente desde Outlook.
- IMAP lectura no marcante; APPEND y MOVE exclusivamente si la implementación existente y las autorizaciones del usuario lo permiten. No activar vías existentes deshabilitadas sin un gate independiente.
- Operaciones externas inciertas (`uncertain`): nunca reintentar escritura automáticamente; reconciliación read-only y evidencia de unicidad antes de resolver.
- Registro de revisiones, snapshots inmutables, auditoría, prevención de duplicados y respeto del hilo de correo.
- Secrets mediante Windows Keyring, no frontend/SQLite/log/GitHub. No exponer cuerpo de correos reales a AI Studio ni modelos externos sin autorización y políticas existentes.
- CRM: integración **solo mediante API**; prohibidas escrituras directas sobre BD del CRM.
- POST sensibles: defensas CSRF, Host, Origin, control de sesión y autorización del actor; evitar XSS/CORS abierto y dependencias CDN en runtime local sin evaluación.
- Mantener la política de modelo IA remoto ya aprobada en CORE; no transferir secretos a frontend.

## 3. Coordinación precisa de herramientas y GitHub
**Roles:**
- **Aider (local):** audita ambos árboles, propone arquitectura, coordina incorporación y revisión, diseña tests e inspecciona diffs; ejecuta cambios solo en TARGET y solo tras aprobación del plan.
- **AI Studio:** fuente del diseño UI y, cuando pueda colaborar vía GitHub, autor de cambios frontend **dentro del repositorio TARGET, en rama de trabajo**. Si su integración GitHub no permite leer/editar ramas o crear PR, documentar la limitación y usar exportación controlada o commits creados localmente por Aider. **No afirmar que la conexión GitHub existe sin verificarla**.
- **GitHub:** repositorio NUEVO y privado dedicado a TARGET; ramas `main`, `integration/*`, `ui/*`, `feature/*`, `fix/*`; Pull Requests y checks. No conectar directamente ni reconfigurar los repositorios originales. Si ya hay Git o remoto en TARGET, inspeccionar antes de crear otros. No subir contenidos antes del escaneo de secretos/datos.
- **Usuario:** define objetivos, autoriza riesgos reales, aprueba plan, gates de fase, conexiones OAuth/IMAP, operaciones externas reales y merge a main. La participación humana se solicita **solo** si el agente carece de autorización suficiente o ante una ambigüedad que afecte alcance, seguridad, datos o compatibilidad.

**Importante:** un repositorio GitHub no sincroniza mágicamente modelos o aplicaciones. Aider y AI Studio deben confirmar la capacidad efectiva de clonar/editar/ramificar/abrir PR; si falta, documentar el paso mínimo humano de conexión/permiso. Nunca solicitar tokens o contraseñas en el chat ni incrustarlos en prompts.

**Flujo por bloque:** issue/ticket con alcance y criterios de aceptación → rama desde main → implementación enfocada → tests offline → revisión de seguridad y diferencias → PR con evidencias → validación humana solo en gate definido → merge aprobado a main. El autor no se autoaprueba la aceptación funcional. Prohibidos commits directos a main después de establecer protecciones. Cada PR debe enumerar archivos, endpoints, migraciones, riesgos, tests, pantallas y reversibilidad.

## 4. FASE 0 — Auditoría inicial (ÚNICA FASE AUTORIZADA AHORA)
Antes de trabajar comprobar permisos y rutas con operaciones **sin escritura**. No instalar, no lanzar pruebas que escriban ni crear repositorio en SOURCES. Inventariar ambos proyectos:
1. Git: estado, rama, HEAD, remoto, tags y diferencias locales, sin modificar Git; detectar código no versionado relevante sin exponer contenido sensible.
2. Estructura, frameworks, versiones, gestores de dependencias, frontend real (React/Vite/TS/Tailwind u otro), backend, entrypoints, puertos, packaging, integraciones y configuración.
3. Pantallas, rutas, componentes, navegación, sistema de diseño, assets, estados vacíos, responsive; separar UI operativa de datos simulados. No copiar licencias/assets sin verificar derechos.
4. Backend Codex: endpoints, servicios, modelos SQLAlchemy/SQLite, Alembic, permisos, máquinas de estados, lógica IMAP, Calendar, drafts, MOVE y CRM; identificar qué está verdaderamente habilitado en UI/CLI.
5. Tests: mapa por módulo y comandos seguros ejecutables en copia aislada; no confiar en recuentos históricos. Detectar cobertura faltante y puntos débiles.
6. Contratos frontend/backend: modelos, DTO/schema, errores, paginación, filtros, ordenación, idempotencia, estados, autenticación local, CSRF, cambios de versión.
7. Dependencias y licencias, riesgo de secretos y PII, necesidad de compilación offline, condiciones de instalación Windows.
8. Evaluación objetiva de rutas de integración: **A)** portar UI AI Studio a endpoints FastAPI existentes; **B)** conservar server rendering y migrar estilo/componentes; **C)** adaptación híbrida. Comparar tiempo, regresiones, seguridad, testabilidad y coste de mantenimiento; **recomendar una** sin asumir A por defecto.
9. Elegir baseline de backend y estrategia de migraciones **solo después de verificar el repositorio real**. Toda BD local nueva debe ser independiente; migraciones Alembic compatibles con esquema vigente; rollback y backup previsto antes de cualquier prueba de migración sobre datos reales, que requiere autorización.

### Informe requerido al acabar FASE 0
Crear **solo en TARGET**, una vez comprobado que no se pisa nada, estos archivos de documentación (nunca ejecutar código funcional):
- `docs/audit/source-inventory.md` — árbol/resumen y evidencia verificable de ambos proyectos (rutas relativas y hashes/commits, sin secretos).
- `docs/audit/feature-matrix.md` — filas por función, columnas UI-AIStudio, CORE-Codex, evidencia, dependencia, riesgo, decisión adoptada.
- `docs/audit/api-gap.md` — contrato endpoint↔pantalla y carencias reales, con clasificación crítica.
- `docs/audit/architecture-options.md` — comparación A/B/C, propuesta y ADRs pendientes.
- `docs/plan/implementation-roadmap.md` — bloques ordenados, dependencias, estimaciones relativas S/M/L, criterios de aceptación y riesgos.
- `docs/plan/verification-matrix.md` — tests por bloque, comandos offline, smoke local, criterios STOP.
- `docs/plan/decision-log.md` — decisiones tomadas, pendientes y consultas humanas agrupadas.
- `docs/plan/operating-contract.md` — reglas de ramas, PR, intervención humana, datos y economía de tokens.
- `README.md` — objetivo, fase actual y cómo reproducir la auditoría, sin prometer que ya existe una aplicación integrada.
Si TARGET no existe, se puede crear exclusivamente para guardar documentación de FASE 0; si ya contiene trabajo, inspeccionarlo primero y NO sobrescribir. **No realizar copia masiva del proyecto CORE durante FASE 0**. No crear nuevas funciones ni rediseñar ninguna pantalla en esta fase.

### Entrega a usuario (formato estricto)
Informe ejecutivo de máximo dos páginas más enlaces a los ocho documentos, con: (1) recomendación técnica justificada, (2) matriz de capacidades con evidencias, (3) lista priorizada de gaps, (4) fases con aceptación, (5) riesgos y mitigaciones, (6) preguntas bloqueantes reales, (7) prueba de que los SOURCES permanecen inalterados mediante estado Git/huellas antes y después de la inspección. No preguntar por detalles deducibles de los repositorios. Finalizar exactamente con `ESTADO: ESPERANDO APROBADO PLAN`.

## 5. Plan orientativo de integración (Aider debe refinarlo, no ejecutarlo aún)
- **G0 Auditoría y arquitectura.** Aprobación explícita del roadmap y de la estrategia A/B/C.
- **G1 Baseline controlado.** Nuevo repositorio privado; importar el backend elegido **sin historial sensible** y sin datos; instalar en TARGET; fixtures sintéticos; tests baseline y scripts de arranque reproducibles. Gate: baseline sin regresión.
- **G2 Shell visual.** Trasladar navegación/layout y tokens visuales de AI Studio con datos de prueba; screenshots comparativas. Gate: diseño aprobado y cero acciones falsas presentadas como reales.
- **G3 Correo y análisis.** Conectar UI a API real, paginación, hilos, filtros, revisiones y errors. Gate: pruebas contractuales, funcionales, seguridad.
- **G4 Tareas y siguientes pasos.** Materialización y estados persistentes, revisión versionada. Gate: invariantes y tests.
- **G5 Calendario y borradores.** UI conectada a backend existente; snapshots, permisos, uncertain y no SMTP. Gate: offline y, solo autorizado, smoke externo controlado.
- **G6 Notas, WhatsApp manual y CRM API.** Sin introducir webhook antes de decisión independiente. Gate: datos persistentes e integración CRM testada en stub.
- **G7 MOVE/archivado y reconciliación.** Respetar funcionalidades deshabilitadas: propuesta separada, pruebas exhaustivas y autorización específica de ejecución real; jamás activar por mera existencia de botón.
- **G8 Hardening/entrega.** Instalación Windows, launcher, respaldo, migración compatible, accesibilidad, usabilidad, documentación de operación, pruebas regresión y release etiquetado.
Estos bloques son **hipótesis de planificación**, no compromisos ni autorización. Aider puede subdividir/reordenar tras la auditoría, preservando gates.

## 6. Criterios de aceptación obligatorios de cada bloque
Todos los siguientes: (a) Scope Lock sin archivos inesperados; (b) diffs y changelog legibles; (c) funciones reales sin mock en producción, errores visibles y estados vacíos honestos; (d) tests automatizados nuevos + regresión aplicable, logs de PASS/FAIL con entorno; (e) seguridad sin regresión y sin secretos; (f) esquema/migraciones compatibles sin tocar datos reales; (g) pruebas UX de los flujos afectados; (h) PR revisable y explicación de rollback; (i) verificación de SOURCE_UI y SOURCE_CORE no modificados; (j) gate de aprobación humana para merge o acceso real. Si falla algún criterio: `REJECT / FIX`, no avanzar.

**Definición de 'funciona':** UI muestra datos persistidos realmente; petición llega al backend real; base de datos temporal recibe el cambio previsto; refresco mantiene el estado; errores y duplicados se controlan; auditoría constata el evento; tests reproducibles. Un toast de éxito o una respuesta mock NO es evidencia.

## 7. Reglas de autonomía y consulta humana
**Autónomo:** leer repositorios, listar y comparar código, investigar dependencias con fuentes ya disponibles, ejecutar tests aislados en TARGET cuando la fase lo permita, refactorizar dentro del alcance, escribir docs, crear ramas y commits de trabajo, abrir PR si la cuenta lo autoriza, solucionar errores confinados al bloque sin alterar contratos, revisar diff y actualizar documentación técnica.

**Requiere autorización:** aprobar arquitectura y roadmap; crear/compartir recursos GitHub si permisos o visibilidad son ambiguos; cambiar contratos/DB en producción; activar integraciones reales o transmitir información comercial; cambiar políticas de seguridad, modelo remoto, costos o servicios cloud; ejecutar escrituras IMAP/Calendar reales; conectar credenciales/OAuth; merge a main; publicar release/instalador; operar sobre los SOURCES (este protocolo no autoriza ninguna escritura en ellos).

**STOP inmediato:** pérdida o riesgo de datos, intentos de modificar SOURCE, exposición de secretos, incertidumbre sobre DB productiva, tests críticos fallidos, acciones externas duplicables, cambio arquitectónico no aprobado o desacuerdo sobre alcance. Formular una única consulta consolidada: `BLOQUE | EVIDENCIA | IMPACTO | OPCIÓN RECOMENDADA | ALTERNATIVAS | DECISIÓN NECESARIA`. No interrumpir por detalles de diseño menores o triviales que pueda inferir y probar.

## 8. Política de ahorro de tokens y gestión del contexto
- Comenzar cada bloque leyendo **solo** su ticket, contratos y archivos implicados; no reinyectar repositorios enteros ni 1200 líneas del MF en cada turno.
- Mantener `docs/context/PROJECT_STATE.md` (estado vigente, HEAD, rama, hechos aprobados, pendientes) y `docs/context/DECISIONS.md` (ADRs compactos) una vez autorizado trabajo, y citarlos en prompts nuevos.
- Priorizar `git diff --stat`, búsqueda dirigida, manifest de símbolos/rutas y lectura por fragmentos; agrupar preguntas relacionadas; presentar máximo 3 decisiones bloqueantes por ciclo, salvo seguridad.
- Separar tareas por módulo, acotar archivos (Scope Lock) y criterios de aceptación. No pedir a AI Studio que regenere toda la aplicación al conectar un endpoint.
- Una herramienta por responsabilidad: AI Studio para interfaz visual; Aider para revisión, integración backend y tests. No duplicar código trabajado en paralelo sobre el mismo archivo; asignar ownership por carpeta/PR.
- Usar los tests focales mientras se desarrolla y suite completa en gates/release; no omitir tests críticos. Informar recuentos reales y skips, nunca inventarlos.
- Consolidar el estado en GitHub issues/PR y docs de TARGET, no depender de la memoria del chat. Usar instrucciones breves reproducibles basadas en rutas.
- Commits pequeños con mensajes operativos; si contexto se agota, emitir handoff de 10–20 líneas con rama, HEAD, alcance, decisiones y próximo paso.

## 9. Protocolo de órdenes entre Aider, AI Studio y usuario
Formato de ticket: `ID | OBJETIVO | FUENTE DE VERDAD | ARCHIVOS PERMITIDOS | NO-TOCAR | CONTRATOS | TESTS | GATE | STOP`. Una vez aprobado G0, Aider redactará tickets atómicos para AI Studio (solo UI) y tickets técnicos para sí mismo; cada ticket identifica endpoints existentes, datos de prueba, estados de loading/error/empty y prohibición de mocks permanentes.

**Plantilla para AI Studio (solo después de G0):**
> Trabaja únicamente en la rama y rutas autorizadas del repositorio privado `asistente-comercial-gemini`. Aplica el ticket [ID] y sus contratos de API adjuntos. Reutiliza el diseño visual y componentes auditados del proyecto UI de referencia. No cambies backend, esquemas ni reglas de negocio; no uses datos reales. Debes entregar un commit/PR con archivos afectados, capturas y tests o, si tu integración GitHub no admite commits/PR, un cambio exportable versionado para revisión local. Prohibido indicar éxito cuando el backend no confirma la operación. Detente ante cambios de alcance o permisos.

**Plantilla de revisión Aider:**
> Revisa el PR [ID] frente al ticket, contratos FastAPI, seguridad, persistencia y UX. Ejecuta tests aplicables en TARGET con datos sintéticos. Reporta `ACCEPT`/`REJECT`, hallazgos por severidad, commits y pruebas; NO hagas merge y NO edites SOURCES. Si REJECT, formula una única corrección focal para AI Studio o Aider, sin ampliar alcance.

## 10. Primera orden que debe recibir Aider — copiar literalmente
> INICIA EXCLUSIVAMENTE FASE 0 del documento `PROTOCOLO_INTEGRACION_AIDER_AISTUDIO_ACLIMAR.md`. Comprueba que las rutas SOURCE_UI y SOURCE_CORE existen y trátalas como SOLO LECTURA estricta, incluido Git y datos. Verifica TARGET antes de crear archivos. Audita UI real, backend real, endpoints, migraciones, tests, brechas y seguridad. No implementes, instales ni migres nada. Genera los documentos de auditoría y roadmap indicados SOLO en TARGET, compara tres alternativas técnicas, justifica una y agrupa decisiones bloqueantes. Verifica que los SOURCES permanecen intactos. Finaliza `ESTADO: ESPERANDO APROBADO PLAN`.

## 11. Comprobaciones manuales previas (usuario)
1. En el PC, confirmar que Aider puede **leer** ambas carpetas, pero seleccionar TARGET como `cwd`; **nunca** arrancar Aider con SOURCES como directorio de edición.
2. Proporcionar a Aider este protocolo y los dos anexos originales como **documentación de referencia** (sin enviar secretos ni contenido comercial a servicios remotos).
3. Asegurar que AI Studio y Aider disponen del mecanismo de colaboración GitHub autorizado; si no, dejarlo como tarea bloqueante de conexión, no fingir trabajo compartido.
4. Antes de cualquier `git push`, verificar `.gitignore`, `git status`, secret scan y archivos staging; GitHub repository privado.
5. No ejecutar todavía la fase G1; primero leer y aprobar el resultado de FASE 0.

## 12. Referencias explícitas y límites de conocimiento
Este protocolo se basa en el Master File adjunto y en la autodescripción adjunta de AI Studio; **ninguno ofrece una auditoría reproducible del árbol local actual**. En particular, el texto de AI Studio sostiene que hay persistencia, Keyring, Calendar, MIME, CRM API y auditoría, pero Aider deberá demostrarlo en código y pruebas. El MF es anterior a fases posteriores del CORE y no se debe tomar como fotografía actual. El propio acceso local a C:\Users\a4863\... **solo está disponible para los agentes que se ejecuten en ese ordenador**; este documento no ha inspeccionado esas carpetas.
