# Engine — Cerebro del sistema de llenado de formularios

Contiene la lógica de coordinación, detección, búsqueda y selección de estrategias.
Es el núcleo que orquesta todo el flujo de llenado.

## Scripts

### `orchestrator.py`
**FormFillerOrchestrator** — Coordina el ciclo completo de llenado de un lead.

1. Prepara el estado de llenado (normaliza tipo de formulario y nivel)
2. Navega a la landing page
3. Prepara el formulario según su tipo (Lateral, Footer, Tarjeta)
4. Detecta el scope del formulario
5. Obtiene la strategy `IFormFiller` vía `registry.py`
6. Crea `FillContext` con los datos del lead (email, nombre ficticio, teléfono ficticio)
7. Ejecuta `filler.fill(ctx)`
8. Retorna `None` (éxito) o `str` (error)

Métodos clave:
- `fill(lead)` → ciclo completo del lead (con `_timeout_error()` para errores de timeout por etapa)
- `_prepare_fill_state(lead)` → `normalize_form_type()` + `resolve_level()` + logs
- `_navigate_to_lp(url)` → navega y espera estabilización (`_soft_wait_network()`)
- `_prepare_form(level)` → delega en `filler.prepare()` y prepara footer/tarjeta
- `_prepare_footer_flow()` → scroll a `#FooterBLC`
- `_prepare_tarjeta(level)` → Plan A (`#TarjetaBLC` existe) / Plan B (buscar LP de producto)
- `_find_scope()` → detecta el contenedor del formulario
- `_execute_strategy(scope, level, lead)` → FillContext + filler.fill() + logs de campos

### `detectors.py`
**FormDetector** — Detecta y analiza formularios en landing pages.

- `detect_form_scope(form_type, tarjeta_product_opened)` → localiza el contenedor del formulario por form_type (`#TarjetaBLC`, `#FooterBLC`, `#LateralBLC`). Retorna None si tarjeta sin LP de producto abierta
- `read_form_state()` → lee valores actuales de campos (modalidad, área, programa, nombre, email, teléfono, checkbox). Usa `FORM_STATE_SELECTORS` de `form_configs.py`
- `log_fields(moment)` → loguea todos los input/select/textarea del scope para debugging

### `form_utils.py`
**Funciones puras** — Sin dependencia de Playwright. Testeables standalone.

- `normalize_text(value)` → lowercase, sin acentos, solo alfanumérico y espacios
- `canonical_level(level)` → normaliza nivel académico (Maestría → Maestria)
- `level_preferences(level)` → lista de variantes del nivel ordenadas por preferencia
- `modality_preferences(level)` → lista de variantes de modalidad según el nivel
- `normalize_form_type(form_type)` → normaliza tipo de formulario (Targeta → tarjeta)
- `is_mexico_universidad_lp(country, url)` → True si es LP de universidad.utel.edu.mx
- `resolve_level(country, lead_nivel)` → traduce lead.nivel a nivel canónico según el país
- `get_form_id(form_type)` → retorna el id del contenedor del formulario

### `program_search.py`
**ProgramSearchEngine** — Busca programas en landing pages y navega a LP de producto (Plan B Tarjeta).

- `select_random_program(level)` → escribe área en input programa y selecciona uno al azar del dropdown
- `open_tarjeta_product(level, original_url)` → abre LP de producto con reintentos si Cloudflare bloquea
- `search_program_from_generic_page(level, original_url)` → busca programa desde página genérica
- `for_country(country, page, form_scope)` → factory: retorna `LupaProgramSearchEngine` (con lupa del navbar) o la base

### `registry.py`
**Registry** — Selecciona la strategy `IFormFiller` correcta según país y URL.

- `get_filler(country, landing_url, page, fake_data)` → retorna siempre una instancia de `IFormFiller` (nunca None). Países CMS → `CmsFiller` con su config de `CMS_CONFIGS`. Universidad México / país sin config → `FallbackFiller` con mensaje de error.

## Diagrama de flujo

```
                         LEAD desde Sheets                                           
                              │                                                      
                              ▼                                                      
┌───────────────────────────────────────────────────────────────────────────────┐    
│                    FormFillerOrchestrator.fill(lead)                          │    
│                              │                                               │     
│  ┌───────────────────────────┼───────────────────────────────────────────┐   │     
│  │  _prepare_fill_state()   │  normalize_form_type() + resolve_level()   │   │     
│  │                          │  form_utils.py                             │   │     
│  └───────────────────────────┼───────────────────────────────────────────┘   │     
│                              │                                               │     
│  ┌───────────────────────────┼───────────────────────────────────────────┐   │     
│  │  _navigate_to_lp(url)    │  page.goto() + _soft_wait_network()        │   │     
│  └───────────────────────────┼───────────────────────────────────────────┘   │     
│                              │                                               │     
│  ┌───────────────────────────┼───────────────────────────────────────────┐   │     
│  │  _prepare_form(level)    │  1. filler.prepare(form_type, level)      │   │      
│  │                          │     → CmsFiller.prepare()                 │   │      
│  │                          │       (lateral: Plan A CTA / Plan B       │   │      
│  │                          │        menú hamburguesa)                  │   │      
│  │                          │  2. Según form_type:                      │   │      
│  │                          │                                            │   │     
│  │  ┌────────┐ ┌──────────┐ │ ┌───────────┐  ┌──────────────────────┐   │   │      
│  │  │ FOOTER │ │ TARJETA  │ │ │ Plan B    │  │ ProgramSearchEngine  │   │   │      
│  │  │        │ │          │ │ │ (Tarjeta):│  │ .open_tarjeta_       │   │   │      
│  │  │ scroll │ │ Plan A:  │ │ │ buscar LP │  │ product(level)       │   │   │      
│  │  │ a      │ │ #Tarjeta │ │ │ de produc-│  │  ó                   │   │   │      
│  │  │ Footer │ │ BLC existe│ │ │ to        │  │ .search_program_     │   │   │     
│  │  │ BLC    │ │ → fill   │ │ │           │  │ from_generic_page()  │   │   │      
│  │  │        │ │ directo  │ │ └───────────┘  └──────────────────────┘   │   │      
│  │  └────────┘ └──────────┘ │                                            │   │     
│  └───────────────────────────┼───────────────────────────────────────────┘   │     
│                              │                                               │     
│  ┌───────────────────────────┼───────────────────────────────────────────┐   │     
│  │  _find_scope()           │  FormDetector.detect_form_scope(           │   │     
│  │                          │    form_type, tarjeta_product_opened)      │   │     
│  │                          │  (detectors.py)                            │   │     
│  └───────────────────────────┼───────────────────────────────────────────┘   │     
│                              │                                               │     
│  ┌───────────────────────────┼───────────────────────────────────────────┐   │     
│  │  _execute_strategy()     │                                           │   │      
│  │                          │                                           │   │      
│  │  1. log_fields() antes   │──► detectors.py                           │   │      
│  │                          │                                           │   │      
│  │  2. Crear FillContext     │──► contracts/fill_context.py             │   │      
│  │     (scope, level,       │                                           │   │      
│  │     email, name, phone)  │                                           │   │      
│  │                          │                                           │   │      
│  │  3. filler.fill(ctx)     │──► CmsFiller / FallbackFiller (fillers/)  │   │      
│  │     (strategy del        │     → handlers/* (select_handler,         │   │      
│  │      registry)           │       contact_fields, privacy_handler,    │   │      
│  │                          │       form_submitter)                     │   │      
│  │                          │     → detectors.read_form_state()         │   │      
│  │                          │     → SubmissionValidator                 │   │      
│  │                          │                                           │   │      
│  │  4. log_fields() después │──► detectors.py                           │   │      
│  │                          │                                           │   │      
│  └───────────────────────────┼───────────────────────────────────────────┘   │     
│                              │                                               │     
│                              ▼                                               │     
│                    Optional[str] (None = éxito, str = error)                  │    
└───────────────────────────────────────────────────────────────────────────────┘    
                              │                                                      
                              ▼                                                      
              pipeline/orchestrator.py recibe el resultado                           
              y escribe en Sheets / notifica al frontend                             
                                                                                     
═══════════════════════════════════════════════════════════════════════════════      
                                                                                     
                  MAPA DE DEPENDENCIAS ENTRE SCRIPTS                                 
                                                                                     
┌──────────────────────────────────────────────────────────────────────────────┐     
│                            engine/                                           │     
│                                                                              │     
│  ┌────────────────┐                                                         │      
│  │  form_utils.py  │◄────────┐                                              │      
│  │  (pure funcs)   │         │                                              │      
│  └────────────────┘         │                                              │       
│            │                │                                              │       
│            │ usado por      │ usado por                                     │      
│            ▼                │                                              │       
│  ┌────────────────┐        │                                              │        
│  │  detectors.py   │────────┤                                              │       
│  └────────┬───────┘        │                                              │        
│           │                │                                              │        
│  ┌────────▼───────┐        │                                              │        
│  │  orchestrator   │────────┘                                              │       
│  │  .py            │                                                       │       
│  └────────┬───────┘                                                       │        
│           │                                                                │       
│           │ usa                                                             │      
│           ▼                                                                │       
│  ┌────────────────┐        ┌──────────────────┐                            │       
│  │  registry.py    │───────│   FillContext     │                            │      
│  │  (selecciona    │       │   (contracts/)    │                            │      
│  │   strategy)     │       └──────────────────┘                            │       
│  └───────┬────────┘                                                       │        
│          │                                                                 │       
│          │ retorna IFormFiller                                             │       
│          ▼                                                                 │       
│  CmsFiller / FallbackFiller (fillers/) + handlers/*                        │       
│                                                                              │     
│  ┌────────────────┐                                                         │      
│  │  program_search │── usado por orchestrator._prepare_tarjeta()            │      
│  │  .py            │   (Plan B: buscar LP de producto)                      │      
│  │                 │── usado por CmsFiller._select_program_input()          │      
│  │                 │   (programa por autocompletado, Chile)                 │      
│  └────────────────┘                                                         │      
└──────────────────────────────────────────────────────────────────────────────┘     
                                                                                     
═══════════════════════════════════════════════════════════════════════════════      
                                                                                     
                    FLUJO DE DATOS DEL LEAD                                          
                                                                                     
 Sheets ──► pipeline/orchestrator.py                                                 
                │                                                                    
                ▼                                                                    
           FormFillerOrchestrator.fill(lead)                                         
                │                                                                    
                ├── lead.landing_url   → page.goto()                                 
                ├── lead.form_type     → normalize_form_type()                       
                ├── lead.nivel         → resolve_level()                             
                ├── lead.test_email    → FillContext → ContactFieldFiller.set_email()
                ├── FakeDataService    → FillContext → ContactFieldFiller.set_name() 
                ├── FakeDataService    → FillContext → ContactFieldFiller.set_phone()
                │                                                                    
                ▼                                                                    
           Optional[str]  →  pipeline/orchestrator.py                                
                                │                                                    
                                ├── None     → sheets.write_success()                
                                ├── str      → sheets.write_error()                  
                                └── siempre  → events.queue.emit() al frontend       
```
