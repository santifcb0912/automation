# InConcert Package — Diagrama de flujo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNO AL PAQUETE                                 │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────────────────┐   │
│  │  Orchestrator     │  │  config/          │  │  automation/browser.py  │   │
│  │  orchestrator.py  │  │  settings.py      │  │  BrowserManager        │   │
│  │                   │  │  countries.py     │  │  human_delay()         │   │
│  └────────┬──────────┘  └────────┬─────────┘  └───────────┬─────────────┘   │
│           │                      │                        │                  │
│  ┌────────▼──────────────────────▼────────────────────────▼─────────────┐   │
│  │                                                                       │   │
│  │               automation/inconcert/                                   │   │
│  │                                                                       │   │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │   │
│  │  │  inconcert_client.py — InConcertClient                          │  │   │
│  │  │                                                                  │  │   │
│  │  │  __init__(page, country)                                         │  │   │
│  │  │    ├─ self.auth = InConcertAuth(page)                            │  │   │
│  │  │    ├─ self.search = InConcertSearch(page, contacts_url)          │  │   │
│  │  │    └─ contacts_url = _build_contacts_url()                       │  │   │
│  │  └──────────┬───────────────────────────────────────────────────────┘  │   │
│  │             │                                                          │   │
│  │  ┌──────────▼───────────────────────────────────────────────────────┐  │   │
│  │  │  1. login()                                                      │  │   │
│  │  │     goto(home) → goto(contacts) → InConcertAuth.login()         │  │   │
│  │  └──────────┬───────────────────────────────────────────────────────┘  │   │
│  │             │                                                          │   │
│  │  ┌──────────▼───────────────────────────────────────────────────────┐  │   │
│  │  │  2. search_lead(email)                                            │  │   │
│  │  │     → InConcertSearch.search(email) → _perform_search()          │  │   │
│  │  └──────────┬───────────────────────────────────────────────────────┘  │   │
│  │             │                                                          │   │
│  │  ┌──────────▼───────────────────────────────────────────────────────┐  │   │
│  │  │  3. prepare_screenshot_view() → Optional[str]                     │  │   │
│  │  │     open_actions_menu() → click_gestionar()                       │  │   │
│  │  │     → expand_creation_section() → expand_contact_section()       │  │   │
│  │  └──────────────────────────────────────────────────────────────────┘  │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│           ┌──────────────────┼──────────────────┐                            │
│           ▼                  ▼                  ▼                            │
│  ┌────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐     │
│  │  auth.py        │  │  search.py       │  │  screenshot.py           │     │
│  │  InConcertAuth  │  │  InConcertSearch │  │  ScreenshotManager       │     │
│  │                 │  │                  │  │                          │     │
│  │  login()        │  │  search(email)   │  │  take_and_upload()       │     │
│  │   ├─_is_logged  │  │   └─_perform_    │  │   ├─_take_screenshot()  │     │
│  │   │  _in()      │  │     search()     │  │   │  (page.screenshot)  │     │
│  │   ├─_fill_      │  │      ├─_ensure_  │  │   └─_upload_to_drive_   │     │
│  │   │  username() │  │      │  contacts()│  │     with_retries()      │     │
│  │   ├─_fill_      │  │      ├─_select_  │  │      └─_upload_to_drive │     │
│  │   │  password() │  │      │  email_    │  │         ├─ MediaIoBase  │     │
│  │   └─_click_     │  │      │  filter()  │  │         │  Upload       │     │
│  │     login_      │  │      ├─_find_     │  │         ├─_make_file_   │     │
│  │     button()    │  │      │  search_   │  │         │  public()     │     │
│  │                 │  │      │  input()   │  │         └─ link raíz    │     │
│  │                 │  │      └─retry_     │  │            Drive        │     │
│  │                 │  │        search()   │  │                          │     │
│  │                 │  │         ├─_click_ │  │                          │     │
│  │                 │  │         │  search_│  │                          │     │
│  │                 │  │         │  button │  │                          │     │
│  │                 │  │         └─_has_   │  │                          │     │
│  │                 │  │           results │  │                          │     │
│  │                 │  │                  │  │                          │     │
│  │                 │  │  open_actions_   │  │                          │     │
│  │                 │  │  menu(email)     │  │                          │     │
│  │                 │  │  click_gestionar │  │                          │     │
│  │                 │  │  ()              │  │                          │     │
│  │                 │  │  _expand_section │  │                          │     │
│  │                 │  │  (text, verify)  │  │                          │     │
│  │                 │  │  expand_creation │  │                          │     │
│  │                 │  │  _section()      │  │                          │     │
│  │                 │  │  expand_contact_ │  │                          │     │
│  │                 │  │  section()       │  │                          │     │
│  └────────────────┘  └──────────────────┘  └──────────────────────────┘     │
│                                                                             │
│  Conexiones externas:                                                        │
│  ┌──────────────┬──────────────────────────────────────────────────┐        │
│  │ Componente   │ Lo usa InConcert para...                         │        │
│  ├──────────────┼──────────────────────────────────────────────────┤        │
│  │ settings.py  │ inconcert_user, inconcert_password                │        │
│  │ countries.py │ country.inconcert_url                             │        │
│  │ google_auth  │ get_google_credentials()                         │        │
│  │ browser.py   │ human_delay()                                    │        │
│  │ orchestrator │ Llama a InConcertClient + ScreenshotManager       │        │
│  │ web/app.py   │ Crea singleton de ScreenshotManager               │        │
│  └──────────────┴──────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Resumen del flujo

```
Orchestrator
│
├─ 1. InConcertClient(page, country)
│     └─ __init__() → crea InConcertAuth + InConcertSearch
│
├─ 2. login()
│     └─ goto(home) → goto(contacts) → auth.login()
│          ├─ _is_logged_in() → si hay sesion, OK
│          └─ si no: _fill_username() → _fill_password() → _click_login_button()
│
├─ 3. search_lead(email)
│     └─ search.search(email)
│          └─ _perform_search()
│               ├─ _ensure_contacts_page()
│               ├─ _select_email_filter() → Email
│               ├─ _find_search_input() → fill(email)
│               └─ retry_search() (8 intentos c/15s)
│                    ├─ _click_search_button()
│                    └─ _has_results() → true/false
│
├─ 4. prepare_screenshot_view()
│     ├─ search.open_actions_menu() → hover row → 3 puntos
│     ├─ search.click_gestionar() → expect_navigation
│     ├─ Esperar "Gestionar Contacto" panel
│     ├─ search.expand_creation_section() → "Creación" → "Origen Id"
│     └─ search.expand_contact_section() → "Contacto" → "Programa de interés"
│
└─ 5. screenshot_manager.take_and_upload(page, country, email)
     ├─ _take_screenshot() → page.screenshot(type="png") → (bytes, filename)
     └─ _upload_to_drive_with_retries() (3 intentos)
          └─ _upload_to_drive()
               ├─ MediaIoBaseUpload → sube bytes a raíz de Drive
               ├─ _make_file_public() → anyone reader
               └─ Retorna link https://drive.google.com/file/d/{id}/view
```
