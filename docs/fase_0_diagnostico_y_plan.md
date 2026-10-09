# FASE 0: Diagnóstico Inicial, Matriz de Funcionalidades y Plan de Integración

**Proyecto:** ACLIMAR Assistant  
**Fase:** 0 (Análisis, Diagnóstico y Planificación)  
**Estado:** COMPLETADA Y FIRMADA  
**Entorno de Ejecución:** Local-only (`127.0.0.1`), Windows  
**Documentos de Referencia:**  
- `MF_Lovable_ACLIMAR_Assistant.md` (Master File / Contrato Funcional)  
- `AIStudio_creacion_asistente.txt` (Resumen de implementación/especificación)  
- Protocolo de Skills: `.coder-skills/Analista.md`, `.coder-skills/Implementador.md`, `.coder-skills/Revisor.md`

---

## 1. Diagnóstico Inicial

### 1.1 Objetivo del Asistente
Centralizar y estructurar la operativa comercial diaria de un delegado comercial B2B de ACLIMAR, actuando como cockpit local de apoyo a la toma de decisiones. La IA asiste extrayendo hechos, tareas, compromisos y propuestas a partir de correo IMAP, WhatsApp manual, notas y CRM, pero **nunca actúa de forma autónoma en el exterior**.

### 1.2 Invariantes de Seguridad y Arquitectura
1. **Local-Only Estricto:** Exclusivamente en `127.0.0.1`. Sin multiusuario, sin auth pública en nube.
2. **Cero Envío de Correo (Cero SMTP):** No existe `SMTP`, no hay envío automático ni botón "Enviar". Todo correo saliente se prepara como snapshot inmutable RFC 2822/MIME y se deposita en la carpeta dedicada `INBOX.Drafts.Borradores Asistente` mediante `IMAP APPEND`. El envío lo realiza el comercial manualmente desde Microsoft Outlook.
3. **Control Humano y Separación de Fases:**
   $$\text{Fuente} \rightarrow \text{Análisis IA} \rightarrow \text{Propuesta} \rightarrow \text{Revisión Humana (Aceptar/Rechazar)} \rightarrow \text{Materialización/Preparación} \rightarrow \text{Aprobación Expresa} \rightarrow \text{Ejecución Externa} \rightarrow \text{Auditoría}$$
   La aceptación de una propuesta no equivale a la autorización de ejecución externa.
4. **Almacenamiento de Secretos:** Credenciales gestionadas a través de Windows Keyring; nunca en SQLite, TOML, logs, git ni frontend.
5. **Acceso al CRM:** Exclusivamente vía API REST local. Prohibida la conexión directa o manipulación del archivo `crm.db`.
6. **Manejo de Ambigüedad e Incertidumbre:** Operaciones externas con respuesta ambigua o timeout pasan al estado `uncertain`, prohibiendo reintentos automáticos a ciegas y exigiendo reconciliación en modo solo lectura (`read-only`).

### 1.3 Estado Actual Detectado y Brecha Técnica
- **Completado según MF:** IMAP read-only (inbox/sent), reconstrucción de hilos, análisis IA, revisión humana, materialización de tareas/siguientes pasos, Google OAuth (calendario Alex Google) con creación verificada, snapshot MIME inmutable de borradores locales, invalidación/reemplazo auditable, base de datos SQLite con migraciones hasta `0011`.
- **Fase 1 (Phase 6N-E) [COMPLETADA]:** Implementación del modelo `EmailDraftAction`, máquina de estados determinista (`submitting`, `created`, `uncertain`, `failed_retryable`, `failed_terminal`), servicio `ImapDraftAppender` con destino `'INBOX.Drafts.Borradores Asistente'`, flag `\Draft`, inyección de cabecera de idempotencia `X-Assistant-Draft-Id` y protocolo de reconciliación en modo `readonly=True`.
- **Fase 2 [COMPLETADA]:** Exposición de endpoints REST en FastAPI (`src/api/drafts_router.py`) con DTOs Pydantic v2, persistencia transaccional y protección contra reintentos ciegos (`409 Conflict`).
- **Fase 3 [COMPLETADA]:** Suite End-to-End (E2E), verificación de cobertura integral y script de despliegue local seguro (`src/run_local.py`) con bind exclusivo en `127.0.0.1`.
- **Fase 3.1 (Verificación Integral y Regresión de Seguridad) [COMPLETADA]:** Suite de pruebas del flujo comercial completo (`tests/test_e2e_complete_flow.py`) y suite de invariantes de seguridad (`tests/test_security_invariants.py`).

---

## 2. Matriz de Funcionalidades

| Módulo / Dominio | Funcionalidad Específica | Estado / Madurez | Dependencia Externa / Interna | Requisitos de Aprobación / Restricciones |
| :--- | :--- | :--- | :--- | :--- |
| **Dashboard / Cockpit** | Métricas de correos nuevos, propuestas pendientes, agenda diaria, alertas | Especificado / MVP | FastAPI, SQLite | Vista agregada. Solo lectura. |
| **Correo (Ingesta)** | Lectura IMAP incremental con `BODY.PEEK`, Inbox/Sent, threading | Implementado / Verificado | Servidor IMAP ACLIMAR (`imap.aclimar.es:993`) | Read-only. Prohibido alterar flags/mensajes remotos. |
| **Análisis IA** | Extracción estructurada: Resumen, Preguntas, Compromisos, Tareas, Next Steps | Implementado / Verificado | API LLM (Gemini 3.8 Flash / configurable) | Genera solo propuestas (`proposed`). Datos externos tratados como no confiables. |
| **Revisión Humana** | Aceptar, Rechazar, Editar (nueva revisión append-only) | Implementado / Verificado | SQLite (modelos de propuesta y revisión) | Las decisiones son terminales por versión. No modifica contenido aceptado silenciosamente. |
| **Tareas** | Transición de `proposed` $\rightarrow$ `pending` $\rightarrow$ `completed` / `cancelled` | Implementado | SQLite | Requiere materialización explícita del usuario tras aceptar propuesta. |
| **Siguientes Pasos** | Transición de `proposed` $\rightarrow$ `planned` $\rightarrow$ `completed` / `cancelled` | Implementado | SQLite | Base para preparación de eventos de Google Calendar. |
| **Google Calendar** | Snapshot de evento $\rightarrow$ aprobación $\rightarrow$ API Google Calendar | Implementado / Verificado | Google Calendar API ("Alex Google") | Solo calendario propio verificado. Sin asistentes, sin recurrencia. Aprobación previa explícita. Manejo de `uncertain`. |
| **Borradores (Local)** | `EmailDraftProposal` $\rightarrow$ `EmailDraftRevision` $\rightarrow$ `EmailDraftAction` inmutable | Implementado | SQLite | Snapshot MIME inmutable RFC 2822. Trazabilidad de reemplazos/invalidaciones. |
| **Borradores (IMAP)** | Depósito vía `IMAP APPEND` en `INBOX.Drafts.Borradores Asistente` | Implementado / Verificado | Servidor IMAP ACLIMAR | Cero SMTP. Máquina de estados (`uncertain`, `submitting`, `created`, `failed`). Reconciliación read-only. |
| **CRM Sync** | Ingesta de empresas/contactos, sincronización de actividades | Especificado | CRM REST API | Solo API REST local. Prohibido tocar `crm.db` directamente. |
| **WhatsApp / Notas** | Ingesta manual de texto/conversaciones para análisis | Especificado | SQLite | Datos tratados como texto plano no confiable. |

---

## 3. Matriz de Brechas y Estrategia de Mitigación

1. **Brecha 1: Concurrencia e Incertidumbre en IMAP APPEND:**
   - *Riesgo:* Creación duplicada de borradores si se produce timeout tras enviar datos.
   - *Mitigación:* Transición obligatoria a `uncertain`, inyección de cabecera `X-Assistant-Draft-Id` y prohibición de reintentos ciegos sin reconciliación previa en modo `readonly=True`.
2. **Brecha 2: Riesgo de Envío Accidental de Correo:**
   - *Riesgo:* Existencia de transportes SMTP o comandos no controlados.
   - *Mitigación:* Invariante estricta: cero librerías SMTP en el flujo de borradores; únicamente `IMAP APPEND` con flags `\Draft`.
3. **Brecha 3: Gestión de Secretos en Entorno Windows:**
   - *Riesgo:* Filtrado accidental de credenciales IMAP/Google en SQLite o repositorios.
   - *Mitigación:* Uso exclusivo de Windows Keyring y sanitización estricta de logs de error.

---

## 4. Plan de Ejecución por Fases

- **Fase 0 (Completada):** Diagnóstico inicial, matriz de funcionalidades, especificación de invariantes y mapa de riesgos.
- **Fase 1 (Completada - Phase 6N-E):** Implementación y aseguramiento del modelo `EmailDraftAction`, servicio de `IMAP APPEND` hacia `'INBOX.Drafts.Borradores Asistente'`, máquina de estados determinista y suite de pruebas unitarias/mockeada.
- **Fase 2 (Completada):** Integración de persistencia y servicios de aplicación/API REST en FastAPI (`src/api/drafts_router.py`).
- **Fase 3 (Completada):** Pruebas End-to-End (E2E), verificación de cobertura integral, suite de regresión de seguridad y despliegue local seguro (`src/run_local.py`).
- **Fase 4 (Siguiente):** Integración con la interfaz web local desacoplada (Lovable UI).

---

## 5. Declaración de Cierre de Fase 0, 1, 2 y 3

Todas las fases han sido ejecutadas, validadas con suites completas de pruebas unitarias, de integración, E2E y de regresión de invariantes de seguridad bajo las directrices estrictas de Cero SMTP y Local-Only (`127.0.0.1`).
