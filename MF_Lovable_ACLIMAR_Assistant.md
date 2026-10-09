# MF — ACLIMAR Assistant
## Master File para recreación en Lovable

**Nombre del producto:** ACLIMAR Assistant  
**Tipo:** Asistente comercial local, single-user  
**Usuario objetivo:** Delegado/comercial B2B  
**Idioma de la interfaz:** Español  
**Plataforma objetivo:** Aplicación web local para Windows  
**Backend actual:** FastAPI + Python + SQLite  
**Frontend actual:** Jinja2 / HTML server-rendered  
**Modo de operación:** local-only, sin multiusuario y sin autenticación pública  
**Bind permitido:** `127.0.0.1` únicamente  
**Principio central:** la IA propone; el usuario revisa y aprueba; ninguna acción externa sensible se ejecuta sin autorización explícita.

---

# 1. Objetivo general

ACLIMAR Assistant es una aplicación para centralizar y asistir la actividad comercial diaria de un delegado B2B.

La aplicación debe:

- Leer y organizar correo corporativo mediante IMAP.
- Reconstruir conversaciones de correo.
- Analizar correos con IA.
- Extraer:
  - resúmenes;
  - preguntas;
  - compromisos;
  - tareas;
  - siguientes pasos.
- Permitir revisión humana de cada propuesta.
- Materializar tareas y siguientes pasos solo tras aprobación.
- Crear eventos en Google Calendar únicamente tras aprobación expresa.
- Preparar respuestas de correo como borradores locales.
- Crear posteriormente esos borradores en una carpeta IMAP específica, pero **nunca enviar correos automáticamente**.
- Mantener trazabilidad y auditoría completa.
- Servir como capa inteligente encima de toda la actividad comercial.

---

# 2. Filosofía funcional

Toda acción debe seguir, cuando aplique, este patrón:

```text
Fuente
→ análisis
→ propuesta
→ revisión humana
→ aceptación/rechazo
→ preparación
→ aprobación explícita de ejecución
→ acción externa
→ auditoría
```

Reglas obligatorias:

1. La IA nunca ejecuta directamente una acción externa.
2. La aceptación de contenido no equivale a autorización de ejecución.
3. Las operaciones externas deben estar claramente separadas de la revisión.
4. Toda acción importante debe dejar rastro auditable.
5. No debe existir ningún botón o flujo que permita enviar correos automáticamente.
6. El sistema debe detenerse ante datos ambiguos en vez de inventar información.

---

# 3. Arquitectura funcional

## 3.1 Fuentes

### Correo corporativo
Cuenta corporativa gestionada mediante IMAP.

Funciones:

- descubrimiento de carpetas;
- lectura read-only;
- sincronización incremental;
- persistencia de cabeceras y contenido;
- reconstrucción de conversaciones;
- distinción entre Inbox y Sent;
- análisis comercial posterior.

La lectura debe usar mecanismos equivalentes a `BODY.PEEK` para no alterar el estado remoto.

### Google Calendar

Cuenta personal Google usada para agenda.

La app puede:

- listar calendarios propios;
- seleccionar un calendario;
- preparar eventos;
- crear eventos solo tras aprobación explícita;
- reconciliar resultados remotos.

No crear eventos de forma automática a partir de una propuesta.

### Notas comerciales

Entrada manual para:

- reuniones;
- llamadas;
- visitas;
- acuerdos;
- observaciones;
- información comercial relevante.

### WhatsApp

MVP:

- copiar/pegar manual de conversaciones o resúmenes.

Fase futura:

- webhook/API si es viable.

### CRM local ACLIMAR

Integración exclusivamente por API.

Regla:

> ACLIMAR Assistant nunca escribe directamente en la base de datos del CRM.

---

# 4. Navegación principal

La aplicación debe tener una navegación lateral o superior clara con estas áreas:

```text
Inicio
Correo
Análisis
Tareas
Siguientes pasos
Calendario
Borradores
Notas
WhatsApp
CRM
Auditoría
Configuración
```

El diseño debe priorizar productividad comercial, no apariencia de aplicación genérica.

---

# 5. Pantalla Inicio / Dashboard

Objetivo: mostrar qué requiere atención.

## Widgets principales

### Correos pendientes de análisis
Mostrar:

- número de correos nuevos;
- conversaciones nuevas;
- análisis pendientes;
- análisis completados.

### Acciones pendientes de revisión
Mostrar:

- tareas propuestas;
- siguientes pasos propuestos;
- borradores pendientes;
- acciones esperando aprobación.

### Agenda
Mostrar:

- próximos eventos;
- siguientes pasos con fecha;
- acciones vencidas;
- tareas para hoy.

### Alertas
Ejemplos:

- propuesta aceptada pero no materializada;
- evento preparado pero no creado;
- borrador preparado pero no creado;
- fallo de integración;
- acción en estado `uncertain`.

---

# 6. Correo

## 6.1 Listado

Mostrar columnas:

- fecha;
- remitente;
- asunto;
- carpeta;
- conversación;
- estado de análisis;
- estado comercial;
- indicador de acción pendiente.

Filtros:

- Inbox / enviados;
- analizado / no analizado;
- cliente;
- conversación;
- rango de fechas;
- con acciones pendientes.

## 6.2 Detalle

Debe mostrar:

### Cabecera
- remitente;
- destinatarios disponibles;
- asunto;
- fecha;
- carpeta;
- conversación;
- Message-ID solo como dato técnico oculto o expandible.

### Contenido
Visualización limpia del cuerpo.

### Análisis IA
Bloques separados:

- Resumen
- Preguntas
- Compromisos
- Tareas propuestas
- Siguientes pasos

Cada propuesta debe mostrar:

- contenido;
- fuente;
- estado;
- botones de revisión.

---

# 7. Revisión humana

Estados:

```text
not_reviewed
accepted
rejected
```

Reglas:

- aceptar/rechazar debe ser explícito;
- aceptación ligada a una versión exacta;
- accepted y rejected son terminales para esa revisión;
- la revisión debe registrar actor y timestamp;
- no modificar silenciosamente contenido aceptado.

Botones:

```text
Aceptar
Rechazar
Editar y crear nueva revisión
```

---

# 8. Tareas y siguientes pasos

## Tarea

Estados operativos:

```text
proposed
pending
completed
cancelled
```

Una tarea propuesta solo se convierte en `pending` mediante materialización explícita.

## Siguiente paso

Estados:

```text
proposed
planned
completed
cancelled
```

Un siguiente paso aceptado se materializa como `planned`.

Debe mostrar:

- texto;
- fuente;
- fecha propuesta;
- estado de revisión;
- estado operativo;
- procedencia;
- acciones disponibles.

---

# 9. Google Calendar

## Flujo

```text
NextStep accepted
→ materialización a planned
→ preparar evento
→ revisar snapshot
→ aprobar creación
→ crear evento en Google Calendar
```

Nunca crear automáticamente.

## Calendario seleccionado

Nombre visible actual:

```text
Alex Google
```

Solo se permiten calendarios propios verificados.

## Evento

Campos:

- título;
- inicio;
- fin;
- zona horaria;
- descripción.

MVP:

- evento temporizado;
- sin asistentes;
- sin recurrencia;
- sin recordatorios automáticos;
- sin eventos de día completo.

## Estados CalendarAction

```text
prepared
submitting
created
uncertain
failed_retryable
failed_terminal
cancelled
```

Reglas:

- `created`, `failed_terminal` y `cancelled` terminales;
- `uncertain` nunca repite automáticamente una creación;
- mantener identificador de cliente estable;
- evitar duplicados.

---

# 10. Borradores de correo

Esta área es crítica.

## Regla absoluta

> ACLIMAR Assistant NO ENVÍA CORREOS.

No debe existir:

- SMTP send;
- botón "Enviar";
- MAIL FROM;
- RCPT TO;
- DATA;
- envío automático.

La entrega final siempre la realiza el usuario manualmente desde Outlook.

---

# 11. Carpeta de borradores

Destino IMAP verificado:

```text
INBOX.Drafts.Borradores Asistente
```

Es una carpeta dedicada creada específicamente para los borradores de la app.

Debe mostrarse en UI con nombre amigable:

```text
Borradores Asistente
```

No debe añadirse a la ingesta normal de correo.

---

# 12. Flujo de borrador

```text
correo origen
→ propuesta de respuesta
→ revisión humana
→ versión aceptada
→ Prepare
→ EmailDraftAction inmutable
→ aprobación explícita "Create mailbox draft"
→ IMAP APPEND
→ borrador visible en Outlook
→ envío manual por el usuario
```

Actualmente el contenido inicial del borrador se introduce de forma humana/local.

La generación AI de respuestas se considera una ampliación futura.

---

# 13. EmailDraftProposal

Representa una propuesta local.

Debe almacenar:

- source_record_id;
- análisis/procedencia;
- conversación;
- contexto crítico;
- timestamp;
- actor.

---

# 14. EmailDraftRevision

Historial append-only.

Campos principales:

- proposal_id;
- versión;
- From;
- To;
- Cc;
- Subject;
- Body;
- timestamp;
- actor;
- revisión anterior.

Reglas:

- inmutable tras creación;
- no Bcc;
- no Reply All automático;
- Cc vacío salvo selección explícita.

---

# 15. EmailDraftReview

Permite:

```text
accepted
rejected
reconfirmed
```

La aceptación queda asociada exactamente a una revisión.

Si el hilo avanza después de una aceptación, la aceptación histórica se conserva, pero antes de preparar debe requerirse reconfirmación.

---

# 16. EmailDraftAction

Snapshot inmutable preparado para futura escritura en buzón.

Campos principales:

- source_record_id;
- conversation_id;
- revision_id;
- review_id;
- accepted_review_id;
- from_address;
- to_json;
- cc_json;
- subject;
- body;
- message_date;
- message_id;
- in_reply_to;
- references_json;
- target_folder;
- payload_digest;
- state;
- actor;
- remote_uid;
- uidvalidity;
- failure_code;
- invalidated_at;
- invalidated_by;
- invalidation_reason;
- invalidation_provenance;
- replaces_action_id.

---

# 17. Estados actuales de EmailDraftAction

Actualmente:

```text
approved
invalidated
```

La siguiente fase amplía a:

```text
approved
submitting
created
uncertain
failed_retryable
failed_terminal
invalidated
```

`invalidated` es terminal.

Una acción invalidada:

- no puede ejecutarse;
- no puede editarse;
- no puede eliminarse;
- conserva su snapshot original.

---

# 18. Reemplazo de acciones inválidas

Si una acción preparada resulta técnicamente defectuosa:

```text
approved
→ invalidated
```

Debe conservar:

- snapshot;
- Date;
- Message-ID;
- digest;
- provenance.

Posteriormente puede prepararse una nueva acción:

```text
invalidated action
→ Prepare Replacement
→ nueva EmailDraftAction
```

El reemplazo:

- tiene nuevo ID;
- nueva Date;
- nuevo Message-ID;
- nuevo digest;
- referencia `replaces_action_id`.

Nunca sobrescribir la acción anterior.

---

# 19. Contrato de destinatarios

## From
Solo identidad de cuenta configurada.

## To
Selección explícita.

El remitente del correo fuente puede proponerse solo si es válido y no ambiguo.

## Cc
Vacío por defecto.

Solo añadir mediante aprobación explícita.

## Bcc
No soportado en MVP.

## Reply All
No existe Reply All automático.

---

# 20. Asunto

Regla determinista:

- si ya empieza por `Re:` ignorando mayúsculas/minúsculas, conservar un único prefijo;
- si no, añadir `Re: `;
- rechazar CR/LF e inyección de cabeceras.

No inventar variantes locales o Fwd/Re adicionales.

---

# 21. Threading de correo

El mensaje fuente debe tener un Message-ID válido.

## In-Reply-To

```text
In-Reply-To = Message-ID del mensaje fuente
```

## References

Si el mensaje fuente no tiene References pero sí un Message-ID válido:

```text
References = source Message-ID
```

Si tiene References válidas:

```text
References =
references existentes
+ source Message-ID
```

Preservar orden.

Eliminar duplicados de forma determinista antes del snapshot.

Si References está malformado:

```text
STOP
```

No reparar heurísticamente.

---

# 22. MIME

Contrato:

- `text/plain`;
- UTF-8;
- quoted-printable;
- CRLF;
- sin HTML;
- sin adjuntos;
- sin imágenes embebidas;
- sin Bcc.

Persistir una sola vez durante Prepare:

- Date;
- Message-ID.

El compositor debe ser determinista.

El digest se calcula sobre los bytes MIME finales.

---

# 23. References y plegado MIME

Requisito importante descubierto durante pruebas.

`References` debe serializarse como secuencia ASCII estructurada de `msg-id`.

Reglas:

- nunca usar encoded-words;
- nunca dividir un msg-id internamente;
- plegar únicamente entre identificadores;
- líneas de continuación comienzan por whitespace;
- preservar orden;
- round-trip exacto;
- respetar límite duro RFC de línea.

Este comportamiento debe mantenerse incluso con cadenas largas de References.

---

# 24. Seguridad

## Local only

La app debe escuchar únicamente en:

```text
127.0.0.1
```

Cualquier otro bind debe ser rechazado.

## Credenciales

Todas las credenciales deben vivir en Windows Keyring.

Nunca:

- SQLite;
- TOML;
- logs;
- UI;
- código fuente.

## Formularios POST

Proteger con:

- sesión;
- CSRF;
- Origin;
- Host;
- actor del proceso;
- PRG;
- no-store.

## Logs

Nunca registrar:

- contraseñas;
- tokens;
- Message-ID completos si no son necesarios;
- bodies de correo;
- MIME completos;
- secretos;
- cookies.

Errores externos deben quedar acotados a códigos seguros.

---

# 25. Auditoría

Registrar eventos importantes:

```text
analysis_completed
proposal_reviewed
task_materialized
next_step_materialized
calendar_action_prepared
calendar_action_submitting
calendar_action_created
draft_action_invalidated
draft_replacement_prepared
draft_append_submitting
draft_append_created
draft_append_uncertain
```

Cada evento debe incluir:

- timestamp;
- actor;
- tipo;
- entidad;
- ID;
- outcome resumido;
- provenance.

No almacenar cuerpos completos innecesariamente.

---

# 26. Estados inciertos

Cualquier operación externa cuya respuesta pueda ser ambigua debe admitir:

```text
uncertain
```

Regla:

> uncertain nunca implica repetir automáticamente una escritura.

Debe existir reconciliación read-only.

---

# 27. Reconciliación de borrador IMAP

Diseño previsto para siguiente fase:

Tras un resultado ambiguo de APPEND:

1. Buscar read-only en la carpeta dedicada.
2. Usar Message-ID persistido como candidato.
3. Verificar además el contenido/digest.
4. Resultado:
   - 0 coincidencias: mantener unresolved;
   - 1 coincidencia exacta: reconciliar a created;
   - múltiples coincidencias: STOP.

Message-ID por sí solo no demuestra unicidad.

---

# 28. UX recomendada

Estética:

- profesional;
- sobria;
- orientada a operaciones B2B;
- alta densidad de información;
- clara separación de estados;
- sin efectos visuales innecesarios.

Usar:

- cards solo para resúmenes;
- tablas para operaciones;
- badges de estado;
- barras laterales;
- panel de detalle;
- modal solo cuando sea necesario.

---

# 29. Semántica visual de estados

## Verde
Acción completada / creada / aceptada.

## Azul
Preparada / planned / información.

## Ámbar
Pendiente de aprobación / requiere atención.

## Rojo
Error terminal / invalidated / bloqueado.

## Gris
Histórico / cancelado / no disponible.

No depender exclusivamente del color: usar texto e iconos.

---

# 30. Pantalla de detalle de borrador

Debe mostrar:

### Fuente
- remitente;
- asunto;
- conversación;
- fecha.

### Revisión
- versión;
- estado;
- actor;
- fecha aceptación.

### Snapshot aprobado
- From;
- To;
- Cc;
- Subject;
- Body.

### Estado técnico
- estado de EmailDraftAction;
- destino `Borradores Asistente`;
- fecha de preparación;
- digest presente;
- Message-ID presente;
- referencia a acción reemplazada si existe.

No mostrar valores técnicos completos salvo modo diagnóstico.

### Acciones

Según estado:

#### propuesta no revisada
```text
Aceptar
Rechazar
Editar
```

#### revisión aceptada sin acción
```text
Prepare
```

#### action approved
```text
Create mailbox draft
```

#### invalidated
```text
Prepare Replacement
```

#### submitting
Sin botón de repetición.

#### uncertain
```text
Reconcile
```

No mostrar botón de APPEND retry directo.

#### created
Mostrar:

```text
Borrador creado en Outlook
```

Sin botón para volver a crear.

---

# 31. Configuración

Secciones:

## Correo
- cuenta;
- host IMAP;
- puerto;
- TLS;
- carpeta Inbox;
- carpeta Sent;
- carpeta Borradores Asistente.

Nunca mostrar contraseña.

## AI
- provider;
- modelo;
- estado;
- habilitado/deshabilitado;
- estado de credencial.

## Google Calendar
- cuenta esperada;
- estado de conexión;
- calendario seleccionado;
- timezone.

## Seguridad
- host local;
- lock operacional;
- estado de credenciales;
- auditoría.

---

# 32. Datos reales que deben asumirse solo como ejemplo visual

No hardcodear estos valores como lógica de negocio.

Ejemplo actual de correo:

```text
Remitente:
gmunoz@grupobertolin.es

Asunto:
Petición oferta - SEGUNDA UNIDAD DE DISTRITO POLICIA LOCAL VALENCIA
```

Ejemplo de borrador de prueba:

```text
Re: Petición oferta - SEGUNDA UNIDAD DE DISTRITO POLICIA LOCAL VALENCIA //Pruebas//
```

El sufijo `//Pruebas//` fue añadido manualmente por el usuario y no forma parte de ninguna regla automática.

---

# 33. Backend y API

Lovable debe tratar la lógica de negocio como backend autoritativo.

Preferencia:

- frontend moderno;
- llamadas REST/JSON al backend FastAPI;
- no duplicar reglas críticas en el navegador;
- validación UI + validación obligatoria backend.

La UI no debe decidir por sí misma:

- estados;
- autorización;
- ownership;
- vigencia;
- unicidad;
- threading;
- reconciliación.

---

# 34. Restricciones de implementación para Lovable

No reemplazar el backend por Supabase/Firebase si el objetivo es integrarse con el producto existente.

No introducir:

- autenticación pública;
- multiusuario;
- servicios cloud innecesarios;
- envío SMTP;
- automatización irreversible sin aprobación;
- escritura directa al CRM;
- lectura de secretos desde frontend.

El frontend debe poder ejecutarse contra:

```text
http://127.0.0.1:<puerto>
```

y mantener el producto local.

---

# 35. Responsive

Prioridad:

1. Desktop Windows.
2. Portátil.
3. Tablet secundaria.

Mobile no es prioritario.

La vista principal debe aprovechar pantallas anchas.

---

# 36. Accesibilidad

- labels visibles;
- focus claro;
- navegación teclado;
- botones con texto, no solo iconos;
- contraste suficiente;
- estados no comunicados solo por color.

---

# 37. Criterio de éxito

Lovable debe producir una aplicación que se sienta como:

> Un cockpit comercial personal que convierte correo, reuniones, agenda y actividad de clientes en acciones estructuradas, pero mantiene al usuario como autoridad final antes de ejecutar cualquier acción externa.

Debe transmitir:

- control;
- trazabilidad;
- seguridad;
- rapidez;
- claridad.

No debe parecer:

- un chatbot genérico;
- un cliente de correo completo;
- un CRM completo;
- una automatización autónoma que actúa sin permiso.

---

# 38. Estado del desarrollo en el momento de este MF

Completado:

- IMAP read-only.
- Sincronización de Inbox y Sent.
- Reconstrucción de conversaciones.
- Análisis AI.
- Revisión humana.
- Materialización de tareas y siguientes pasos.
- Google OAuth.
- Selección de calendario propio.
- Creación controlada y verificada de evento.
- Flujo local de borradores.
- Versionado y aceptación de borradores.
- MIME determinista.
- Invalidación auditable.
- Reemplazo de acciones defectuosas.
- Migraciones hasta `0011`.

Baseline Git relevante:

```text
5c50acf6f790eb7f018b860f07217a73f55acdd5
Implement controlled email draft workflow
```

Siguiente punto técnico pendiente:

```text
Phase 6N-E
Implement controlled IMAP draft APPEND workflow OFFLINE ONLY
```

Esta fase debe comenzar con:

- escritor IMAP dedicado;
- estados submitting/created/uncertain/failure;
- captura APPENDUID cuando exista;
- reconciliación segura;
- cero SMTP;
- tests offline antes de cualquier escritura real.

---

# 39. Instrucción final para Lovable

Construye la interfaz completa respetando este MF como contrato funcional.

Prioriza primero:

1. Shell y navegación.
2. Dashboard.
3. Correo y detalle de análisis.
4. Revisión humana.
5. Tareas / siguientes pasos.
6. Calendar actions.
7. Flujo de borradores.
8. Auditoría.
9. Configuración.

No inventes reglas de negocio ausentes.

Si una operación requiere backend aún no implementado, crea la interfaz en estado:

```text
available_when_backend_ready
```

o equivalente visual, pero no simules éxito real.

Mantén toda acción sensible detrás de una confirmación explícita y conserva una distinción clara entre:

```text
propuesta
aceptación
preparación
ejecución
resultado
```
