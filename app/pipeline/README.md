# Pipeline Package — Diagrama de flujo

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐    
│                                        EXTERNO AL PAQUETE                                             │   
│                                                                                                       │   
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  ┌─────────────┐  ┌─────────────┐          │     
│  │  web/routes/ │  │  events/      │  │  sheets/         │  │  automation/ │  │  config/     │          │ 
│  │  app.py      │  │  queue.py     │  │  reader+writer   │  │  browser +   │  │  settings +  │          │ 
│  │              │  │  EventQueue   │  │  (gspread)       │  │  form +      │  │  countries   │          │ 
│  └──────┬───────┘  └──────┬────────┘  └────────┬─────────┘  │  inconcert   │  └──────┬───────┘          │ 
│         │                 │                     │            └──────┬───────┘         │                  │
│         │                 │                     │                   │                 │                  │
│  ┌──────▼─────────────────▼─────────────────────▼───────────────────▼─────────────────▼──────────────┐  │ 
│  │                                                                                                   │  │ 
│  │                                pipeline/orchestrator.py                                           │  │ 
│  │                                                                                                   │  │ 
│  │  ┌───────────────────────────────────────────────────────────────────────────────────────────┐   │  │  
│  │  │  Orchestrator                                                                              │   │  │ 
│  │  │                                                                                             │   │  │
│  │  │  __init__(sheets_reader, sheets_writer, screenshot_manager, event_queue)                    │   │  │
│  │  │    ├─ self.sheets_reader = SheetsReader (inyectado)                                        │   │  │ 
│  │  │    ├─ self.sheets_writer = SheetsWriter (inyectado)                                        │   │  │ 
│  │  │    ├─ self.screenshot_manager = ScreenshotManager (inyectado)                              │   │  │ 
│  │  │    ├─ self.event_queue: IEventPublisher (inyectado)                                        │   │  │ 
│  │  │    ├─ self._fake_data = FakeDataService(RandomName, RandomPhone)                           │   │  │ 
│  │  │    ├─ self._semaphore = Semaphore(max_workers)                                             │   │  │ 
│  │  │    ├─ self._cancelled = False                                                              │   │  │ 
│  │  │    ├─ self._email_counter = 0 + _counter_lock                                              │   │  │ 
│  │  │    └─ self._process_tasks: list[Task]                                                      │   │  │ 
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  run(request: RunRequest)                                                                 │   │  │  
│  │  │    ┌──────────────────────────────────────────────────────────────────────────────────┐  │   │  │   
│  │  │    │  1. get_country(request.country) → valida país                                  │  │   │  │    
│  │  │    │  2. _execute_country():                                                          │  │   │  │   
│  │  │    │       a. _load_leads(request) → sheets_reader.get_leads(...) → list[LeadRow]    │  │   │  │    
│  │  │    │       b. _filter_by_flow(leads, request) → filtra por flujo (data-driven)        │  │   │  │   
│  │  │    │       c. Sin leads → _emit("done") y termina                                    │  │   │  │    
│  │  │    │       d. sheets_reader.get_column_for_today() → columna G-K                      │  │   │  │   
│  │  │    │       e. BrowserManager.launch() → browser_context                              │  │   │  │    
│  │  │    │       f. _run_all(...) → create_task(_process_lead(...)) por lead + gather       │  │   │  │   
│  │  │    │       g. _emit_summary(results, leads, start_time) → _emit("done")               │  │   │  │   
│  │  │    │  3. finally: browser_manager.close(), mark_finished()                            │  │   │  │   
│  │  │    └──────────────────────────────────────────────────────────────────────────────────┘  │   │  │   
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  _process_lead(lead, country, tab, column, sheet_id, idx, total, browser)                 │   │  │  
│  │  │    └─ async with self._semaphore → _process_single_lead(...)                              │   │  │  
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  _process_single_lead(lead, country, tab, column, sheet_id, idx, total, browser) → bool   │   │  │  
│  │  │                                                                                             │   │  │
│  │  │  ┌──────────────────────────────────────────────────────────────────────────────────────┐  │   │  │ 
│  │  │  │  a. Genera email único: _build_test_email(_next_email_counter())                     │  │   │  │ 
│  │  │  │     → test{date}N{counter:03d}@testingUtel.com (contador atómico con lock)          │  │   │  │  
│  │  │  │  b. _process_lead_steps(...) → orquesta form + InConcert + captura:                  │  │   │  │ 
│  │  │  │                                                                                      │  │   │  │ 
│  │  │  │  ──────────── FORMULARIO ────────────                                               │  │   │  │  
│  │  │  │  c. _emit("processing")                                                              │  │   │  │ 
│  │  │  │  d. _fill_form(browser, country, lead) → new_page()                                  │  │   │  │ 
│  │  │  │  e. FormFillerOrchestrator(page, country, fake_data) → .fill(lead)                   │  │   │  │ 
│  │  │  │  f. Si error → (error, form_page) → corta el lead                                   │  │   │  │  
│  │  │  │                                                                                      │  │   │  │ 
│  │  │  │  ──────────── INCONCERT ─────────────                                               │  │   │  │  
│  │  │  │  g. _inconcert_capture(page, country, lead) → new_page()                             │  │   │  │ 
│  │  │  │  h. InConcertClient(page, country) → .login() → .search_lead(email)                  │  │   │  │ 
│  │  │  │  i. .prepare_screenshot_view() → Optional[str]                                       │  │   │  │ 
│  │  │  │  j. screenshot_manager.take_and_upload(page, country, email) → link                  │  │   │  │ 
│  │  │  │  k. Cualquier error → (error, None, ...) → corta el lead                             │  │   │  │ 
│  │  │  │                                                                                      │  │   │  │ 
│  │  │  │  ──────────── SHEETS ──────────────────                                            │  │   │  │   
│  │  │  │  l. _record_success(...) → sheets_writer.write_success + _emit("success")            │  │   │  │ 
│  │  │  │     (o _emit("partial_success") con warning si falta "Programa de interés")          │  │   │  │ 
│  │  │  └──────────────────────────────────────────────────────────────────────────────────────┘  │   │  │ 
│  │  │                                                                                             │   │  │
│  │  │  Error: finally cierra form_page + inconcert_page (si existen)                             │   │  │ 
│  │  │  Excepción inesperada → _handle_error(... f"error: {e}") → False                           │   │  │ 
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  _handle_error(lead, sheet_id, tab, column, reason)                                       │   │  │  
│  │  │    ├─ sheets_writer.write_error(... reason)  (asyncio.to_thread)                          │   │  │  
│  │  │    └─ _emit("lead_error", {email, url, row, reason, country})                             │   │  │  
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  _filter_by_flow(leads, request) → list[LeadRow]                                         │   │  │   
│  │  │    └─ Sin flow en request → retorna todos                                                │   │  │   
│  │  │    └─ Lee country.flow_url_prefixes[flow] (str o lista de prefijos)                     │   │  │    
│  │  │    └─ Filtra leads cuya landing_url empiece por algún prefijo                           │   │  │    
│  │  │    └─ País sin el flujo → retorna todos (data-driven, sin ifs por país)                 │   │  │    
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  cancel()                                                                                 │   │  │  
│  │  │    ├─ self._cancelled = True                                                              │   │  │  
│  │  │    └─ task.cancel() for each task in self._process_tasks                                  │   │  │  
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  _emit(event_type, data)                                                                  │   │  │  
│  │  │    └─ self.event_queue.emit(event_type, data)  ← SSE al frontend                          │   │  │  
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  │                                                                                                   │  │ 
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │   
│  │  │  Helpers internos                                                                        │   │  │   
│  │  │    └─ _load_leads(request)          → asyncio.to_thread(sheets_reader.get_leads)         │   │  │   
│  │  │    └─ _run_all(leads, country, ...) → tasks paralelas + gather(return_exceptions=True)  │   │  │    
│  │  │    └─ _emit_summary(results, ...)   → calcula éxitos/errores + _emit("done")            │   │  │    
│  │  │    └─ _next_email_counter()         → contador atómico con asyncio.Lock                 │   │  │    
│  │  │    └─ _build_test_email(counter)    → test{ddmmyy}N{nnn}@testingUtel.com                │   │  │    
│  │  │    └─ _record_success(...)          → write_success + _emit("success"/"partial_success")│   │  │    
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │   
│  └───────────────────────────────────────────────────────────────────────────────────────────────────┘  │ 
│                                                                                                         │ 
│  Conexiones externas:                                                                                    │
│  ┌─────────────────────────┬──────────────────────────────────────────────────────────────────┐        │  
│  │ Componente               │ Lo usa Orchestrator para...                                      │        │ 
│  ├─────────────────────────┼──────────────────────────────────────────────────────────────────┤        │  
│  │ sheets/reader.py        │ get_leads() → leer leads de Google Sheets                        │        │  
│  │                         │ get_column_for_today() → columna de resultado del día            │        │  
│  │ sheets/writer.py        │ write_success() → escribir link de captura en Sheets             │        │  
│  │                         │ write_error() → escribir razón de error en Sheets                │        │  
│  │ automation/browser.py   │ BrowserManager → lanza/cierra Chrome persistente                 │        │  
│  │                         │ .new_page() → crea pages para form e InConcert                   │        │  
│  │ automation/form/        │ FormFillerOrchestrator.fill(lead) → llena formulario en LP       │        │  
│  │ automation/inconcert/   │ InConcertClient → login, search, prepare_screenshot               │        │ 
│  │ automation/inconcert/   │ ScreenshotManager.take_and_upload() → captura + Drive            │        │  
│  │ core/models.py          │ LeadRow (DTO) + RunRequest (DTO)                                 │        │  
│  │ core/exceptions.py      │ CountryNotFoundError → país inválido                             │        │  
│  │ core/interfaces/        │ IEventPublisher (Protocol) → EventQueue implementa               │        │  
│  │ core/fake_data/         │ FakeDataService → RandomNameProvider + RandomPhoneProvider       │        │  
│  │ config/settings.py      │ max_workers, lead_timeout_seconds, google_sheet_id               │   │       
│  │ config/countries.py     │ get_country() → valida país, retorna config del país             │   │       
│  │                         │ country.flow_url_prefixes → prefijos de URL por flujo (cms/uni)  │   │       
│  │ events/queue.py         │ EventQueue → implementa IEventPublisher, cola SSE                │   │       
│  │ web/routes.py           │ Crea Orchestrator, llama a .run() en background thread           │        │  
│  │ web/app.py              │ Crea singletons de SheetsReader, SheetsWriter, ScreenshotManager │        │  
│  └─────────────────────────┴──────────────────────────────────────────────────────────────────┘        │  
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Resumen del flujo

```
routes.py /api/run                                                                    
│                                                                                     
│  Crea RunRequest{country, flow, sheet_id, sheet_tab}                                
│  Crea background_thread → asyncio.run(orchestrator.run(request))                    
▼                                                                                     
Orchestrator.run()                                                                    
│                                                                                     
├─ 1. get_country(request.country) → valida existencia                                
│                                                                                     
├─ 2. _execute_country() → _load_leads() → list[LeadRow]                              
│                                                                                     
├─ 3. _filter_by_flow() → data-driven con country.flow_url_prefixes (todos los países)
│                                                                                     
├─ 4. sheets_reader.get_column_for_today() → columna G-K según día                    
│                                                                                     
├─ 5. BrowserManager.launch() → contexto Chrome persistente                           
│                                                                                     
├─ 6. Por cada lead (paralelo, semáforo max_workers):                                 
│     │                                                                               
│     ├─ Genera email único: test{date}N{001}@testingUtel.com                         
│     │                                                                               
│     ├─ _fill_form() → new_page() + FormFillerOrchestrator.fill(lead)                
│     │   └─ Si falla → writer.write_error + emit "lead_error"                        
│     │                                                                               
│     ├─ _inconcert_capture() → new_page() + login() + search_lead(email)             
│     │   └─ Si falla → writer.write_error + emit "lead_error"                        
│     │                                                                               
│     ├─ InConcert → prepare_screenshot_view() + take_and_upload()                    
│     │   └─ Si falla → writer.write_error + emit "lead_error"                        
│     │                                                                               
│     ├─ _record_success() → writer.write_success                                     
│     │                                                                               
│     └─ emit "success" / "partial_success" → cierra pages                            
│                                                                                     
└─ 7. _emit_summary() → Emit "done" con resumen (éxitos, errores, tiempo)             
     → finally: browser_manager.close(), event_queue.mark_finished()                  
```
