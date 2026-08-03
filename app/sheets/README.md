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
│  │  │    └─ por fila → _parse_row(row, idx, country) → LeadRow o None        │  │  │   
│  │  │                                                                         │  │  │  
│  │  │  _parse_row(row, row_idx, country_name)                                │  │  │   
│  │  │    ├─ Salta filas cortas (< 5 celdas) o país vacío                     │  │  │   
│  │  │    ├─ Matchea país sin acentos y bidireccional:                        │  │  │   
│  │  │    │   "Perú"↔"Peru", "El Salvador"↔"Salvador" (col B)                │  │  │    
│  │  │    ├─ Salta filas sin URL (col D); URL con espacios → primera parte    │  │  │   
│  │  │    └─ _normalize_form_type(col E) → FORM_TYPE_MAP (Footer, Tarjeta)    │  │  │   
│  │  │                                                                         │  │  │  
│  │  │  get_column_for_today() → str (G-K según weekday)                      │  │  │   
│  │  │    └─ Lunes→G ... Viernes→K; finde→K (columna de resultados del día)   │  │  │   
│  │  └────────────────────┬───────────────────────────────────────────────────┘  │  │   
│  │                       │                                                       │  │  
│  │  ┌────────────────────▼───────────────────────────────────────────────────┐  │  │   
│  │  │  writer.py — SheetsWriter                                              │  │  │   
│  │  │                                                                         │  │  │  
│  │  │  __init__()                                                            │  │  │   
│  │  │    └─ _connect() → gspread.authorize(credenciales)                     │  │  │   
│  │  │                                                                         │  │  │  
│  │  │  write_success(sheet_id, tab, row, column, link, email)                │  │  │   
│  │  │    ├─ celda = "{column}{row}" (columna del día G-K)                    │  │  │   
│  │  │    └─ _write_with_retries(_do_write, ...) → update(celda, [[link]])    │  │  │   
│  │  │                                                                         │  │  │  
│  │  │  write_error(sheet_id, tab, row, column, email, reason)                │  │  │   
│  │  │    ├─ celda = "{column}{row}"                                          │  │  │   
│  │  │    └─ _write_with_retries → "ERROR - lead no llegó (reason)"           │  │  │   
│  │  │                                                                         │  │  │  
│  │  │  _write_with_retries(write_fn, *args) → hasta 3 intentos con           │  │  │   
│  │  │    reconexión (_connect) y espera de 3s entre intentos                 │  │  │   
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
│  sheet_id, sheet_tab, country, flow                                                   
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
│     ├─ _parse_row() por fila:                                                         
│     │   ├─ Filtra por país (col B, sin acentos, bidireccional)                        
│     │   ├─ Salta filas sin URL (col D)                                                
│     │   └─ Normaliza tipo de formulario (col E → FORM_TYPE_MAP)                       
│     └─ Retorna list[LeadRow]                                                          
│                                                                                       
├─ 2. _filter_by_flow() → filtra por URL según flow (data-driven, todos los países)     
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
│       → worksheet.update("G2", [["ERROR - lead no llegó (reason) - revisión manual"]])
│                                                                                       
└─ Emite "done" con resumen                                                             
```

## Columnas del Sheets

```
Col A       Col B      Col C    Col D              Col E       Col F          
──────────────────────────────────────────────────────────────────────        
(no usada)  País       Nivel    URL Landing       Location    Cliente         
            Mexico     NULL     https://utel...   Footer      Cliente1        
            Peru       NULL     https://peru...   FormLP      Cliente2        
                                  ↓                  ↓                        
                            Column.URL=3     Column.LOCATION=4 → FORM_TYPE_MAP
                                                                              
  Col G-K: columna de resultados del día (write_success / write_error)        
  Lunes→G, Martes→H, Miércoles→I, Jueves→J, Viernes→K (finde→K)               
```
