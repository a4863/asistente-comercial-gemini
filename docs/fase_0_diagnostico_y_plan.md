# FASE 0: Diagnóstico Inicial, Matriz de Funcionalidades y Plan de Integración

**Proyecto:** ACLIMAR Assistant  
**Fase:** 0 (Análisis, Diagnóstico y Planificación)  
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
- **Siguiente Hito Crítico Backend:** `Phase 6N-E` (Ejecución controlada de `IMAP APPEND` offline-first / mockeada para borradores de correo, gestión de estados `submitting`, `created`, `uncertain`, `failed_retryable`, `failed_terminal`).
- **Reto de Integración Frontend (Lovable / Web UI):** Desacoplar vistas Jinja2 a un frontend web estructurado y responsivo (desktop Windows prioritario) conectado mediante API REST con FastAPI en `127.0.0.1`, sin duplicar lógica de negocio en el cliente y manteniendo la semántica visual de estados.

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
| **Borradores (Local)** | `EmailDraftProposal` $\rightarrow$ `EmailDraftRevision` $\rightarrow$ `EmailDraftAction` inmutable | Implementado | SQLite | Snapshot MIME