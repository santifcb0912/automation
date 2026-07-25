# Handlers — Componentes atómicos de interacción DOM

Cada handler encapsula una responsabilidad única sobre el formulario.
Son independientes entre sí: nunca se llaman unos a otros.
El orquestador (`MexicoCmsFiller`) los invoca en secuencia.

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
**PrivacyHandler** — Marca el checkbox de políticas de privacidad.

- `check()` → Plan A: `input[type='checkbox']` con `dispatch_event`. Plan B: 6 selectores de fallback Chakra con `click()`. Retorna True si queda marcado.
- `_is_checked()` → evalúa en el navegador si el checkbox está marcado. Si no existe checkbox, retorna True (no requiere acción).

### `form_submitter.py`
**FormSubmitter** — Envía el formulario.
**SubmissionValidator** — Valida campos pre-submit.

- `FormSubmitter.submit()` → recorre la lista de botones submit (desde `CmsConfig`) y dispara `dispatch_event("click")` en el primero que encuentre
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
│  │  .select()        │   │ .set_name()      │   │ .is_checked()     │        │
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
│  │  │     (dispara click en el    │  │   fields(state)        │   │          │
│  │  │     primer botón submit     │  │   (valida área, progra- │   │          │
│  │  │     que encuentre. Usa      │  │    ma, nombre, email,   │   │          │
│  │  │     dispatch_event para     │  │    teléfono, checkbox)  │   │          │
│  │  │     elementos ocultos/      │  └────────────────────────┘   │          │
│  │  │     fuera de viewport)      │                               │          │
│  │  └─────────────────────────────┘                               │          │
│  └────────────────────────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   │ (los handlers NO se llaman entre sí)
                                   │ todos son invocados por:
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│               MexicoCmsFiller (automation/form/fillers/)                     │
│               ─────────────────────────────────────────                      │
│                                                                              │
│  1. _select_modality()    ──► SelectHandler.select("modality", ...)          │
│  2. _select_area()        ──► SelectHandler.exists("area")                   │
│                                → .select("area", ...)                        │
│  3. _select_program()     ──► SelectHandler.select("program", ...)           │
│                                ó ProgramSearchEngine (engine/)               │
│  4. _fill_contacts()      ──► ContactFieldFiller.set_name()                  │
│                                ContactFieldFiller.set_email()                │
│                                ContactFieldFiller.set_phone()                │
│  5. _check_privacy()      ──► PrivacyHandler.check()                        │
│  6. _validate_pre_submit() ──► FormDetector.read_form_state() (engine/)      │
│                                SubmissionValidator.check_submission_fields() │
│  7. _submit()             ──► FormSubmitter.submit()                        │
└──────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      DEPENDENCIAS EXTERNAS                                   │
│                                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │  Playwright   │   │   loguru     │   │ form_configs │   │  FillContext  │  │
│  │  (Page/Loc.)  │   │  (logger)    │   │ (CmsConfig,  │   │ (contracts/   │  │
│  │               │   │              │   │  submit_but-  │   │  fill_context │  │
│  │  handlers     │   │  handlers    │   │  tons, field  │   │  .py)         │  │
│  │  interactúan  │   │  loguean     │   │  names)       │   │              │  │
│  │  con el DOM   │   │  eventos     │   │              │   │  transporta   │  │
│  │               │   │              │   │  FormSubmit-  │   │  fake_name,   │  │
│  │               │   │              │   │  ter recibe   │   │  test_email,  │  │
│  │               │   │              │   │  submit_but-  │   │  fake_phone   │  │
│  │               │   │              │   │  tons desde   │   │  desde el     │  │
│  │               │   │              │   │  aquí         │   │  orquestador  │  │
│  └──────────────┘   └──────────────┘   └──────┬───────┘   └──────────────┘  │
│                                               │                              │
│                   SelectHandler usa           ▼                              │
│                   field_modality/area/program config/form_configs.py         │
│                   desde CmsConfig             (CmsConfig, MEXICO_CMS_CONFIG) │
│                                               (CMS_CONFIGS dict)             │
└──────────────────────────────────────────────────────────────────────────────┘
```
