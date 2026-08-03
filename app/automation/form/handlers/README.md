# Handlers — Componentes atómicos de interacción DOM

Cada handler encapsula una responsabilidad única sobre el formulario.
Son independientes entre sí: nunca se llaman unos a otros.
El orquestador (`CmsFiller`) los invoca en secuencia.

## Scripts

### `select_handler.py`
**SelectHandler** — Interactúa con elementos `<select>` del formulario.

- `exists(field_name)` → verifica si un `<select>` existe por su name/id
- `select(field_name, preferred, require_preferred_match)` → selecciona una opción usando matching normalizado (sin acentos, mayúsculas ni placeholders). Estrategia: exact match → partial match → primera opción disponible. Dispara eventos input/change/blur para React/Chakra.
- `_wait_for_real_options(select, field_name)` → espera que opciones dinámicas carguen (útil para área, que carga vía AJAX tras seleccionar modalidad)

### `contact_fields.py`
**ContactFieldFiller** — Llena los campos de nombre, email y teléfono.

- `set_name(fake_name)` → busca y llena el campo nombre
- `set_email(test_email)` → busca y llena el campo email
- `set_phone(fake_phone)` → busca y llena el campo teléfono
- `set_input(selectors, value, label)` → genérico: prueba selectores uno por uno, hace `fill()`, verifica con `input_value()`
- `_first_existing(selectors)` → prueba cada selector CSS y retorna el primer locator que exista en el DOM

### `privacy_handler.py`
**PrivacyHandler** — Marca todos los checkboxes del formulario (privacidad y consentimiento).

- `check()` → Plan A (`_check_direct()`): recorre todos los `input[type='checkbox']` y marca con `dispatch_event` solo los desmarcados. Si no quedaron todos marcados → Plan B: 6 selectores de fallback Chakra con `click()`. Retorna True si todos quedan marcados.
- `_check_direct()` → marca cada checkbox desmarcado del formulario
- `_all_checked()` → evalúa en el navegador si TODOS los checkboxes están marcados. Si no hay checkbox, retorna True (no requiere acción).

### `form_submitter.py`
**FormSubmitter** — Envía el formulario.
**SubmissionValidator** — Valida campos pre-submit.

- `FormSubmitter.submit()` → recorre la lista de botones submit (recibida por constructor desde `CmsConfig.submit_buttons`) y dispara `dispatch_event("click")` en el primero que encuentre
- `SubmissionValidator.check_submission_fields(state)` → verifica que área, programa, nombre, email, teléfono y checkbox estén completos. Retorna `None` si ok, o el nombre del campo que falló. Modalidad excluida (usa botones Chakra, no `<select>`).

## Diagrama de flujo

```
┌──────────────────────────────────────────────────────────────────────────────┐  
│                         PAQUETE handlers/                                    │  
│                                                                              │  
│  ┌──────────────────┐   ┌──────────────────┐   ┌───────────────────┐        │   
│  │  select_handler   │   │ contact_fields   │   │  privacy_handler  │        │  
│  │  ───────────────  │   │ ───────────────  │   │ ────────────────  │        │  
│  │  SelectHandler    │   │ ContactField-    │   │ PrivacyHandler    │        │  
│  │  .exists()        │   │ Filler           │   │ .check()          │        │  
│  │  .select()        │   │ .set_name()      │   │ .all_checked()    │        │  
│  └────────┬──────────┘   │ .set_email()     │   └────────┬──────────┘        │  
│           │              │ .set_phone()     │            │                   │  
│           │              │ .set_input()     │            │                   │  
│           │              │ .first_existing()│            │                   │  
│           │              └────────┬─────────┘            │                   │  
│           │                       │                      │                   │  
│  ┌────────┴───────────────────────┴──────────────────────┴────────┐          │  
│  │                     form_submitter.py                          │          │  
│  │                     ─────────────────                          │          │  
│  │  ┌─────────────────────────────┐  ┌────────────────────────┐   │          │  
│  │  │     FormSubmitter           │  │   SubmissionValidator  │   │          │  
│  │  │     .submit()               │  │   .check_submission_   │   │          │  
│  │  │     (recorre submit_buttons │  │   fields(state)        │   │          │  
│  │  │     de CmsConfig y dispara  │  │   (valida área, progra- │   │          │ 
│  │  │     click en el primero.    │  │    ma, nombre, email,   │   │          │ 
│  │  │     Usa dispatch_event      │  │    teléfono, checkbox)  │   │          │ 
│  │  │     para elementos ocultos/ │  └────────────────────────┘   │          │  
│  │  │     fuera de viewport)      │                               │          │  
│  │  └─────────────────────────────┘                               │          │  
│  └────────────────────────────────────────────────────────────────┘          │  
└──────────────────────────────────────────────────────────────────────────────┘  
                                   │                                              
                                   │ (los handlers NO se llaman entre sí)         
                                   │ todos son invocados por:                     
                                   ▼                                              
┌──────────────────────────────────────────────────────────────────────────────┐  
│               CmsFiller (automation/form/fillers/cms_filler.py)             │   
│               ─────────────────────────────────────────                      │  
│                                                                              │  
│  1. _select_modality()      ──► SelectHandler.select("modality", ...)        │  
│  2. _select_eres_bachiller()──► SelectHandler.select("eresBachiller", ...)   │  
│                                 (solo si config.field_eres_bachiller)        │  
│  3. _select_area()          ──► SelectHandler.exists("area")                 │  
│                                 → .select("area", ...)                       │  
│  4. _select_ciudad()        ──► SelectHandler.select("ciudad", ...)          │  
│                                 (solo si config.field_ciudad)                │  
│  5. _select_provincia()     ──► SelectHandler.select("provincia", ...)       │  
│                                 (solo si config.field_provincia)             │  
│  6. _select_program()       ──► select ("program") o autocompletado          │  
│                                 ProgramSearchEngine (engine/)                │  
│  7. _select_pais()          ──► SelectHandler.select("paisesPIVI", ...)      │  
│                                 (Global, solo si config.field_pais)          │  
│  8. _select_canal_preferido()─► SelectHandler.select("Canal_Preferido")      │  
│  9. _fill_contacts()        ──► ContactFieldFiller.set_name()                │  
│                                 ContactFieldFiller.set_email()               │  
│                                 ContactFieldFiller.set_phone()               │  
│  10. _check_privacy()       ──► PrivacyHandler.check()                       │  
│  11. _validate_pre_submit() ──► FormDetector.read_form_state() (engine/)      │ 
│                                 SubmissionValidator.check_submission_fields()│  
│  12. _submit()              ──► FormSubmitter.submit()                       │  
└──────────────────────────────────────────────────────────────────────────────┘  
                                   │                                              
                                   ▼                                              
┌──────────────────────────────────────────────────────────────────────────────┐  
│                      DEPENDENCIAS EXTERNAS                                   │  
│                                                                              │  
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │   
│  │  Playwright   │   │   loguru     │   │ form_configs │   │  FillContext  │  │ 
│  │  (Page/Loc.)  │   │  (logger)    │   │ (CmsConfig,  │   │ (contracts/   │  │ 
│  │               │   │              │   │  CMS_CONFIGS  │   │  fill_context │  │
│  │  handlers     │   │  handlers    │   │  dict)       │   │  .py)         │  │ 
│  │  interactúan  │   │  loguean     │   │              │   │              │  │  
│  │  con el DOM   │   │  eventos     │   │  FormSubmit-  │   │  transporta   │  │
│  │               │   │              │   │  ter recibe   │   │  fake_name,   │  │
│  │               │   │              │   │  submit_but-  │   │  test_email,  │  │
│  │               │   │              │   │  tons desde   │   │  fake_phone   │  │
│  │               │   │              │   │  aquí         │   │  desde el     │  │
│  └──────────────┘   └──────────────┘   └──────┬───────┘   │  orquestador  │  │  
│                                               │            └──────────────┘  │  
│                   SelectHandler usa           ▼                              │  
│                   field_modality/area/program config/form_configs.py         │  
│                   desde CmsConfig             (CmsConfig, MEXICO_CMS_CONFIG  │  
│                                               como ejemplo del dict          │  
│                                               CMS_CONFIGS)                   │  
└──────────────────────────────────────────────────────────────────────────────┘  
```
