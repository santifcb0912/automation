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
│  │  │    ├─ contacts_url = _build_contacts_url()                       │  │   │ 
│  │  │    └─ self.missing_contact_area: bool (flag de captura parcial)  │  │   │ 
│  │  └──────────┬───────────────────────────────────────────────────────┘  │   │ 
│  │             │                                                          │   │ 
│  │  ┌──────────▼───────────────────────────────────────────────────────┐  │   │ 
│  │  │  1. login()                                                      │  │   │ 
│  │  │     goto(home) → goto(contacts) → InConcertAuth.login()         │  │   │  
│  │  │     (polling 20 intentos x 1s hasta confirmar sesión)            │  │   │ 
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
│  │  │     → _wait_management_panel() → espera panel "Gestionar"         │  │   │
│  │  │     → expand_creation_section() → expand_contact_section()        │  │   │
│  │  │     (si "Programa de interés" no aparece → missing_contact_area)  │  │   │
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
│  │  login()        │  │  search(email)   │  │  __init__()              │     │  
│  │   ├─_is_logged  │  │   └─_perform_    │  │   └─_connect_drive()     │     │  
│  │   │  _in()      │  │     search()     │  │   (build drive v3)       │     │  
│  │   ├─_fill_      │  │      ├─_ensure_  │  │                          │     │  
│  │   │  username() │  │      │  contacts()│  │  take_and_upload()       │     │ 
│  │   ├─_fill_      │  │      ├─_select_  │  │   ├─_take_screenshot()   │     │  
│  │   │  password() │  │      │  email_    │  │   │  (page.screenshot,   │     │ 
│  │   └─_click_     │  │      │  filter()  │  │   │   hasta 2 intentos)  │     │ 
│  │     login_      │  │      ├─_find_     │  │   └─_upload_to_drive_    │     │ 
│  │     button()    │  │      │  search_   │  │     with_retries()       │     │ 
│  │                 │  │      │  input()   │  │      └─_upload_to_drive  │     │ 
│  │                 │  │      └─retry_     │  │         (3 intentos con  │     │ 
│  │                 │  │        search()   │  │          _reconnect_     │     │ 
│  │                 │  │         ├─_click_ │  │          drive())        │     │ 
│  │                 │  │         │  search_│  │         ├─ MediaIoBase   │     │ 
│  │                 │  │         │  button │  │         │  Upload        │     │ 
│  │                 │  │         └─_has_   │  │         ├─_make_file_    │     │ 
│  │                 │  │           results │  │         │  public()      │     │ 
│  │                 │  │                  │  │         └─ link raíz      │     │ 
│  │                 │  │  open_actions_   │  │            Drive          │     │ 
│  │                 │  │  menu(email)     │  │                          │     │  
│  │                 │  │  click_gestionar │  │                          │     │  
│  │                 │  │  ()              │  │                          │     │  
│  │                 │  │  _expand_section │  │                          │     │  
│  │                 │  │  (text, verify)  │  │                          │     │  
│  │                 │  │  _find_verifica- │  │                          │     │  
│  │                 │  │  tion(text)      │  │                          │     │  
│  │                 │  │  _scroll_to_sec- │  │                          │     │  
│  │                 │  │  tion_first_     │  │                          │     │  
│  │                 │  │  fields(text)    │  │                          │     │  
│  │                 │  │  expand_creation │  │                          │     │  
│  │                 │  │  _section()      │  │                          │     │  
│  │                 │  │  expand_contact_ │  │                          │     │  
│  │                 │  │  section()       │  │                          │     │  
│  │                 │  │  (scroll_on_     │  │                          │     │  
│  │                 │  │  failure=True)   │  │                          │     │  
│  └────────────────┘  └──────────────────┘  └──────────────────────────┘     │   
│                                                                             │   
│  Conexiones externas:                                                        │  
│  ┌──────────────┬──────────────────────────────────────────────────┐        │   
│  │ Componente   │ Lo usa InConcert para...                         │        │   
│  ├──────────────┼──────────────────────────────────────────────────┤        │   
│  │ settings.py  │ inconcert_user, inconcert_password                │        │  
│  │ countries.py │ country.inconcert_url                             │        │  
│  │ google_auth  │ get_google_credentials()                         │        │   
│  │ core/utils   │ human_delay()                                    │        │   
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
│               └─ polling: 20 intentos x 1s hasta _is_logged_in()              
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
│     ├─ _wait_management_panel() → espera panel "Gestionar Contacto"           
│     ├─ search.expand_creation_section() → "Creación" → "Origen Id"            
│     │     (verificación con _find_verification, tolera acentos)               
│     ├─ search.expand_contact_section() → "Contacto" → "Programa de interés"   
│     │     (scroll_on_failure → _scroll_to_section_first_fields)               
│     └─ Si "Programa de interés" no aparece → missing_contact_area = True      
│          → pipeline emite "partial_success" (captura igual se toma)           
│                                                                               
└─ 5. screenshot_manager.take_and_upload(page, country, email)                  
     ├─ _take_screenshot() → page.screenshot(type="png") → (bytes, filename)    
     │     (hasta 2 intentos con timeout de 20s)                                
     └─ _upload_to_drive_with_retries() (3 intentos con _reconnect_drive)       
          └─ _upload_to_drive()                                                 
               ├─ MediaIoBaseUpload → sube bytes a raíz de Drive                
               ├─ _make_file_public() → anyone reader                           
               └─ Retorna link https://drive.google.com/file/d/{id}/view        
```
