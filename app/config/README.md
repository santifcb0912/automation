# config/ — Diagrama de paquetes

```
┌─────────────────────────────────────────────────────────────────────────────────┐  
│                              config/                                            │  
│                                                                                 │  
│  ┌────────────────┐    ┌──────────────────┐    ┌──────────────────────┐         │  
│  │   settings.py   │    │   countries.py   │    │    google_auth.py    │         │ 
│  │                 │    │                  │    │                      │         │ 
│  │  Pydantic       │    │  @dataclass      │    │  get_google_         │         │ 
│  │  BaseSettings   │    │  Country         │    │  credentials()       │         │ 
│  │                 │    │                  │    │    ├─ Service Account│         │ 
│  │  Lee .env       │    │  COUNTRIES[]     │    │    └─ _get_oauth_    │         │ 
│  │                 │    │  15 países       │    │       credentials()  │         │ 
│  │  Valida rutas   │    │                  │    │         ├─ _load_    │         │ 
│  │  y rangos       │    │  get_country()   │    │         │  oauth_    │         │ 
│  │                 │    │  get_level_name()│    │         │  token()   │         │ 
│  └────────┬────────┘    └────────┬─────────┘    │         ├─ _authorize│         │ 
│           │                      │              │         │  _new_oauth│         │ 
│           │                      │              │         └─ _save_    │         │ 
│           ▼                      │              │            oauth_    │         │ 
│  ┌────────────────────────────────────────────────────┐   │  token()   │         │ 
│  │                  form_configs.py                   │   └──────────┬─┘         │ 
│  │                                                    │              │           │ 
│  │  CmsConfig (dataclass):                            │              │           │ 
│  │    submit_buttons, cta_texts, field_modality,      │              │           │ 
│  │    field_area, field_program, field_provincia,     │              │           │ 
│  │    field_ciudad, field_eres_bachiller,             │              │           │ 
│  │    field_canal_preferido, field_pais,              │              │           │ 
│  │    pais_value_map, level_equivalences              │              │           │ 
│  │                                                    │              │           │ 
│  │  CMS_CONFIGS: dict[str, CmsConfig]                 │              │           │ 
│  │    (mexico, argentina, colombia, peru, ecuador,    │              │           │ 
│  │     usa, bolivia, chile, paraguay, dominicana,     │              │           │ 
│  │     guatemala, panama, el_salvador, global)        │              │           │ 
│  │                                                    │              │           │ 
│  │  FORM_STATE_SELECTORS: selectores para lectura     │              │           │ 
│  │    de estado pre-submit                            │              │           │ 
│  └──────────────────────┬─────────────────────────────┘              │           │ 
│                         │                                            │           │ 
│                         ▼                                            ▼           │ 
│  ┌─────────────────────────────────────────────────────────────────────┐        │  
│  │                         data/                                       │        │  
│  │                                                                     │        │  
│  │  names.json  ─── pool global de 20 nombres (todos los países)       │        │  
│  │                                                                     │        │  
│  │  phones.json ─── templates por país: mx, pe, ec, co, dom, ar,      │        │   
│  │                  bo, cl, usa, sv, hn, pa, py, gt, global           │        │   
│  │                                                                     │        │  
│  │  google_credentials.json        ─── Service Account JSON           │        │   
│  │  google_oauth_client_secret.json ─── OAuth Desktop Client          │        │   
│  │  google_oauth_token.json        ─── Token tras autorizar           │        │   
│  │                                                                     │        │  
│  └─────────────────────────────────────────────────────────────────────┘        │  
└─────────────────────────────────────────────────────────────────────────────────┘  
          │                    │                      │                              
          │  settings          │  countries            │  google_auth                
          ▼                    ▼                      ▼                              
┌─────────────────────┐  ┌──────────────────┐  ┌──────────────────────┐              
│  Dependientes       │  │  Dependientes     │  │  Dependientes        │             
│                     │  │                   │  │                      │             
│  main.py            │  │  form/engine/     │  │  sheets/reader.py    │             
│  web/app.py         │  │   orchestrator    │  │  sheets/writer.py    │             
│  web/routes.py      │  │  form_utils       │  │  inconcert/          │             
│  pipeline/          │  │  detectors        │  │    screenshot.py     │             
│   orchestrator      │  │  registry         │  │                      │             
│  sheets/reader.py   │  │  fillers/cms_     │  │                      │             
│  automation/        │  │   filler          │  │                      │             
│   inconcert/        │  │  inconcert_client │  │                      │             
│    auth             │  │  pipeline/        │  │                      │             
│    screenshot       │  │   orchestrator    │  │                      │             
└─────────────────────┘  └──────────────────┘  └──────────────────────┘              
                                                                                     
    data/ es consumido por:                                                          
    ├─ core/fake_data/providers.py                                                   
    │    ├─ RandomNameProvider  ─→ names.json                                        
    │    └─ RandomPhoneProvider ─→ phones.json                                       
    └─ config/google_auth.py                                                         
         └─ get_google_credentials() ─→ google_credentials.json / google_oauth_*.json
```

## Relaciones entre scripts de config/

| Script | Importa desde | Es importado por |
|---|---|---|
| `settings.py` | — | `google_auth`, `screenshot`, `auth`, `orchestrator`, `reader`, `routes`, `app`, `main` |
| `countries.py` | — | `engine/orchestrator`, `form_utils`, `detectors`, `registry`, `cms_filler`, `inconcert_client`, `orchestrator` |
| `form_configs.py` | — | `registry`, `cms_filler`, `detectors` |
| `google_auth.py` | `settings` | `screenshot`, `reader`, `writer` |
| `data/names.json` | — | `core/fake_data/providers` (lectura directa) |
| `data/phones.json` | — | `core/fake_data/providers` (lectura directa) |
| `data/google_credentials.json` | — | `config/google_auth` (Service Account) |
| `data/google_oauth_client_secret.json` | — | `config/google_auth` (OAuth) |
| `data/google_oauth_token.json` | — | `config/google_auth` (OAuth) |

## Dependencias entre paquetes

```
                    ┌──────────┐                                         
                    │  .env    │                                         
                    └────┬─────┘                                         
                         │                                               
                         ▼                                               
                    ┌──────────┐                                         
                    │ config/  │───→ core/ (data consumido por fake_data)
                    └────┬─────┘                                         
                         │                                               
          ┌──────────────┼──────────────┐                                
          │              │              │                                
          ▼              ▼              ▼                                
    ┌──────────┐   ┌──────────┐   ┌──────────┐                           
    │ pipeline │   │automation│   │  sheets  │                           
    │          │   │          │   │          │                           
    │orchestr. │   │ form/    │   │ reader   │                           
    │          │   │ inconcert│   │ writer   │                           
    └──────────┘   └──────────┘   └──────────┘                           
          │              │                                               
          │              │                                               
          ▼              ▼                                               
    ┌──────────┐   ┌──────────┐                                          
    │  web/    │   │  main.py │                                          
    └──────────┘   └──────────┘                                          
```

## Notas

- `settings.py` es la pieza central — casi todo el sistema depende de ella.
- `google_auth.py` depende de `settings` para leer rutas de credenciales. Flujo OAuth: `_load_oauth_token()` → si no existe token válido, `_authorize_new_oauth()` (abre browser) y `_save_oauth_token()`.
- `countries.py` es independiente (no importa nada del proyecto). Cada `Country` incluye `flow_url_prefixes` (prefijos de URL por flujo cms/universidad, str o tupla) — base del filtrado data-driven de `_filter_by_flow`.
- `data/` agrupa todos los archivos JSON: datos fake (`names.json`, `phones.json`) y credenciales de Google (`google_credentials.json`, etc.).
- Las credenciales están en `.gitignore`; no forman parte del código.
- `config/` no importa nada de `core/`, `automation/`, `sheets/` ni `web/` — es la capa más baja del sistema.
