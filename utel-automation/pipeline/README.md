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
│  │  │    │  2. sheets_reader.get_leads(country, sheet_id, sheet_tab) → list[LeadRow]       │  │   │  │
│  │  │    │  3. _filter_mexico_flow(leads, request) → filtra por flow si México             │  │   │  │
│  │  │    │  4. sheets_reader.get_column_for_today() → columna G-K                           │  │   │  │
│  │  │    │  5. BrowserManager() → launch() → browser_context                                │  │   │  │
│  │  │    │  6. create_task(_process_lead(...)) por cada lead                                │  │   │  │
│  │  │    │  7. gather(*tasks) → espera todos                                               │  │   │  │
│  │  │    │  8. _emit("done") con resumen                                                   │  │   │  │
│  │  │    │  9. finally: browser_manager.close(), mark_finished()                            │  │   │  │
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
│  │  │  │  a. Genera email único: test{date}N{counter:03d}@testingUtel.com                    │  │   │  │
│  │  │  │  b. _emit("processing")                                                             │  │   │  │
│  │  │  │                                                                                      │  │   │  │
│  │  │  │  ──────────── FORMULARIO ────────────                                               │  │   │  │
│  │  │  │  c. browser.new_page() → form_page                                                  │  │   │  │
│  │  │  │  d. FormFillerOrchestrator(page, country, fake_data) → .fill(lead)                  │  │   │  │
│  │  │  │  e. Si falla → _handle_error(... "formulario no enviado") → return False            │  │   │  │
│  │  │  │                                                                                      │  │   │  │
│  │  │  │  ──────────── INCONCERT ─────────────                                               │  │   │  │
│  │  │  │  f. browser.new_page() → inconcert_page                                              │  │   │  │
│  │  │  │  g. InConcertClient(page, country) → .login()                                       │  │   │  │
│  │  │  │  h. Si falla login → _handle_error→ return False                                    │  │   │  │
│  │  │  │  i. inc .search_lead(email) → busca lead en CRM                                     │  │   │  │
│  │  │  │  j. Si no encuentra → _handle_error→ return False                                   │  │   │  │
│  │  │  │  k. inc .prepare_screenshot_view() → Optional[str]                                  │  │   │  │
│  │  │  │  l. Si error → _handle_error→ return False                                          │  │   │  │
│  │  │  │                                                                                      │  │   │  │
│  │  │  │  ──────────── SCREENSHOT ─────────────                                             │  │   │  │
│  │  │  │  m. screenshot_manager.take_and_upload(page, country, email) → link                 │  │   │  │
│  │  │  │  n. Si falla → _handle_error→ return False                                          │  │   │  │
│  │  │  │                                                                                      │  │   │  │
│  │  │  │  ──────────── SHEETS ──────────────────                                            │  │   │  │
│  │  │  │  o. sheets_writer.write_success(sheet_id, tab, row, column, link, email)            │  │   │  │
│  │  │  │                                                                                      │  │   │  │
│  │  │  │  p. _emit("success") → return True                                                  │  │  │   │  │
│  │  │  └──────────────────────────────────────────────────────────────────────────────────────┘  │   │  │
│  │  │                                                                                             │   │  │
│  │  │  Error: finally form_page.close() + inconcert_page.close()                                 │   │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                                                   │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │
│  │  │  _handle_error(lead, sheet_id, tab, column, reason)                                       │   │  │
│  │  │    ├─ sheets_writer.write_error(... reason)  (asyncio.to_thread)                          │   │  │
│  │  │    └─ _emit("lead_error", {email, url, row, reason, country})                             │   │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                                                   │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐   │  │
│  │  │  _filter_mexico_flow(leads, request) → list[LeadRow]                                     │   │  │
│  │  │    └─ Si NO México → retorna todos                                                        │   │  │
│  │  │    └─ Si flow = universidad → filtra startsWith("https://universidad.utel.edu.mx")        │   │  │
│  │  │    └─ Si flow = cms → filtra startsWith("https://utel.edu.mx")                            │   │  │
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
│  │ config/settings.py      │ max_workers, lead_timeout_seconds, google_sheet_id               │        │
│  │ config/countries.py     │ get_country() → valida país, retorna config del país             │        │
│  │ events/queue.py         │ EventQueue → implementa IEventPublisher, cola SSE                │        │
│  │ web/routes.py           │ Crea Orchestrator, llama a .run() en background thread           │        │
│  │ web/app.py              │ Crea singletons de SheetsReader, SheetsWriter, ScreenshotManager │        │
│  └─────────────────────────┴──────────────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Resumen del flujo

```
routes.py /api/run
│
│  Crea RunRequest{country, sheet_id, sheet_tab, mexico_flow}
│  Crea background_thread → asyncio.run(orchestrator.run(request))
▼
Orchestrator.run()
│
├─ 1. get_country(request.country) → valida existencia
│
├─ 2. sheets_reader.get_leads(country, sheet_id, sheet_tab)
│     → list[LeadRow]
│
├─ 3. _filter_mexico_flow() → si es México, filtra por URL universidad/cms
│
├─ 4. sheets_reader.get_column_for_today() → columna G-K según día
│
├─ 5. BrowserManager.launch() → contexto Chrome persistente
│
├─ 6. Por cada lead (paralelo, semáforo max_workers):
│     │
│     ├─ Genera email único: test{date}N{001}@testingUtel.com
│     │
│     ├─ FormFiller → new_page() + FormFillerOrchestrator.fill(lead)
│     │   └─ Si falla → writer.write_error + emit "lead_error"
│     │
│     ├─ InConcert → new_page() + login() + search_lead(email)
│     │   └─ Si falla → writer.write_error + emit "lead_error"
│     │
│     ├─ InConcert → prepare_screenshot_view()
│     │   └─ Si falla → writer.write_error + emit "lead_error"
│     │
│     ├─ ScreenshotManager.take_and_upload() → link Drive
│     │   └─ Si falla → writer.write_error + emit "lead_error"
│     │
│     ├─ writer.write_success(row, column, link, email)
│     │
│     └─ emit "success" → cierra pages
│
└─ 7. Emit "done" con resumen (éxitos, errores, tiempo)
     → finally: browser_manager.close(), event_queue.mark_finished()
```
