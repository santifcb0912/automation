# Sheets Package — Diagrama de flujo

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNO AL PAQUETE                                      │
│                                                                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────────────────┐   │
│  │  Orchestrator     │  │  config/          │  │  config/google_auth.py        │   │
│  │  orchestrator.py  │  │  settings.py      │  │  get_google_credentials()     │   │
│  │                   │  │  google_sheet_id  │  └──────────────┬─────────────────┘   │
│  └────────┬──────────┘  └────────┬─────────┘                 │                     │
│           │                      │                           │                     │
│  ┌────────▼──────────────────────▼───────────────────────────▼──────────────────┐  │
│  │                                                                               │  │
│  │                              sheets/                                          │  │
│  │                                                                               │  │
│  │  ┌────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  reader.py — SheetsReader                                              │  │  │
│  │  │                                                                         │  │  │
│  │  │  __init__()                                                            │  │  │
│  │  │    └─ _connect() → gspread.authorize(credenciales)                     │  │  │
│  │  │                                                                         │  │  │
│  │  │  get_leads(country_name, sheet_id, sheet_tab)                          │  │  │
│  │  │    ├─ open_by_key(sheet_id) → libro                                    │  │  │
│  │  │    ├─ worksheet(sheet_tab) → pestaña                                   │  │  │
│  │  │    ├─ get_all_values() → list[list[str]]                               │  │  │
│  │  │    └─ filtra por país + URL → list[LeadRow]                            │  │  │
│  │  │                                                                         │  │  │
│  │  │  get_column_for_today() → str (G/K)                                    │  │  │
│  │  │    └─ Mapea datetime.weekday() a columna de resultados                 │  │  │
│  │  └────────────────────┬───────────────────────────────────────────────────┘  │  │
│  │                       │                                                       │  │
│  │  ┌────────────────────▼───────────────────────────────────────────────────┐  │  │
│  │  │  writer.py — SheetsWriter                                              │  │  │
│  │  │                                                                         │  │  │
│  │  │  __init__()                                                            │  │  │
│  │  │    └─ _connect() → gspread.authorize(credenciales)                     │  │  │
│  │  │                                                                         │  │  │
│  │  │  write_success(sheet_id, tab_name, row_number, column, link, email)    │  │  │
│  │  │    ├─ worksheet.update("F{row}", [[link]])                              │  │  │
│  │  │    └─ Escribe link de Drive en la celda                                 │  │  │
│  │  │                                                                         │  │  │
│  │  │  write_error(sheet_id, tab_name, row_number, column, email, reason)    │  │  │
│  │  │    ├─ worksheet.update("F{row}", [["ERROR - ..."]])                     │  │  │
│  │  │    └─ Escribe mensaje de error en la celda                              │  │  │
│  │  └────────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                               │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                │                                                    │
│              ┌─────────────────┴─────────────────┐                                   │
│              ▼                                   ▼                                   │
│  ┌──────────────────────┐            ┌──────────────────────┐                        │
│  │  Google Sheets API   │            │  Google Sheets API   │                        │
│  │  Lectura (GET)       │            │  Escritura (PUT)     │                        │
│  │                      │            │                      │                        │
│  │  - open_by_key       │            │  - update cell       │                        │
│  │  - worksheet         │            │                      │                        │
│  │  - get_all_values    │            │                      │                        │
│  └──────────────────────┘            └──────────────────────┘                        │
│                                                                                      │
│  Conexiones externas:                                                                 │
│  ┌──────────────┬─────────────────────────────────────────────────────────┐         │
│  │ Componente   │ Lo usa sheets para...                                    │         │
│  ├──────────────┼──────────────────────────────────────────────────────────┤         │
│  │ settings.py  │ No necesita config de sheets (sheet_id viene del front)  │         │
│  │              │ google_credentials_path para auth                         │         │
│  │ google_auth  │ get_google_credentials() → autoriza gspread.Client       │         │
│  │ core/models  │ LeadRow — estructura de datos que retorna get_leads()    │         │
│  │ orchestrator │ Llama a SheetsReader.get_leads() y SheetsWriter          │         │
│  │ web/app.py   │ Crea singletons de SheetsReader + SheetsWriter           │         │
│  │ web/routes   │ Pasa sheet_id y sheet_tab desde el formulario frontend   │         │
│  └──────────────┴──────────────────────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────────────────────────────────────┘
```

## Resumen del flujo

```
Frontend (formulario)
│
│  sheet_id, sheet_tab, country
▼
routes.py → RunRequest
│
▼
Orchestrator.run()
│
├─ 1. reader.get_leads(country, sheet_id, sheet_tab)
│     ├─ gspread.authorize() con Service Account
│     ├─ open_by_key(sheet_id) → abre el libro
│     ├─ worksheet(sheet_tab) → selecciona pestaña
│     ├─ get_all_values() → descarga todas las celdas
│     ├─ Filtra por país (col B)
│     ├─ Salta filas sin URL (col D)
│     ├─ Normaliza tipo de formulario (col E → FORM_TYPE_MAP)
│     └─ Retorna list[LeadRow]
│
├─ 2. _filter_mexico_flow() → filtra por URL si es México CMS/Universidad
│
├─ 3. reader.get_column_for_today() → columna G-K según día
│
├─ 4. Por cada lead:
│     └─ Procesa con Playwright (formulario + InConcert + screenshot)
│
│     ─ Si éxito:
│       writer.write_success(sheet_id, tab, row, column, link, email)
│       → worksheet.update("G2", [["https://drive.google.com/..."]])
│
│     ─ Si error:
│       writer.write_error(sheet_id, tab, row, column, email, reason)
│       → worksheet.update("G2", [["ERROR - timeout 2 min - revisión manual"]])
│
└─ Emite "done" con resumen
```

## Columnas del Sheets

```
Col A       Col B      Col C    Col D              Col E       Col F
──────────────────────────────────────────────────────────────────────
Nombre      País       Nivel    URL Landing       Location    Cliente
Lead 1      Mexico     NULL     https://utel...   Footer      Cliente1
Lead 2      Peru       NULL     https://peru...   FormLP      Cliente2
                                  ↓                  ↓
                            Column.URL=3     Column.LOCATION=4 → FORM_TYPE_MAP
```
