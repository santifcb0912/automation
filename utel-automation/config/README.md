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
│  │                 │    │                  │    │                      │         │
│  │  Lee .env       │    │  COUNTRIES[]     │    │  GOOGLE_SCOPES[]     │         │
│  │                 │    │  15 países       │    │                      │         │
│  │  Valida rutas   │    │                  │    │  service_account     │         │
│  │  y rangos       │    │  get_country()   │    │    (default)         │         │
│  │                 │    │  get_level_name()│    │                      │         │
│  └────────┬────────┘    └────────┬─────────┘    │  oauth (opcional)    │         │
│           │                      │              └──────────┬───────────┘         │
│           │                      │                         │                    │
│           ▼                      │                         ▼                    │
│  ┌────────────────────────────────────────────────────────────────────┐         │
│  │                         data/                                      │         │
│  │                                                                    │         │
│  │  names.json  ─── pool global de 20 nombres (todos los países)      │         │
│  │                                                                    │         │
│  │  phones.json ─── templates por país: mx, pe, ec, co, dom, ar,     │         │
│  │                  bo, cl, usa, sv, hn, pa, py, gt, global          │         │
│  │                                                                    │         │
│  │  google_credentials.json        ─── Service Account JSON           │         │
│  │  google_oauth_client_secret.json ─── OAuth Desktop Client          │         │
│  │  google_oauth_token.json        ─── Token tras autorizar           │         │
│  │                                                                    │         │
│  └────────────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────────┘
          │                    │                           │
          │  settings          │  countries                │  google_auth
          ▼                    ▼                           ▼
┌─────────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│  Dependientes       │  │  Dependientes     │  │  Dependientes        │
│                     │  │                   │  │                      │
│  main.py            │  │  form_filler_orch │  │  sheets/reader.py    │
│  web/app.py         │  │  form_utils       │  │  sheets/writer.py    │
│  web/routes.py      │  │  detectors        │  │  inconcert/          │
│  pipeline/          │  │  inconcert_client │  │    screenshot.py     │
│   orchestrator      │  │  pipeline/        │  │                      │
│  sheets/reader.py   │  │   orchestrator    │  │                      │
│  automation/        │  │  tests/conftest   │  │                      │
│   inconcert/        │  │                   │  │                      │
│    auth             │  │                   │  │                      │
│    screenshot       │  │                   │  │                      │
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
| `countries.py` | — | `form_filler_orch`, `form_utils`, `detectors`, `inconcert_client`, `orchestrator`, `conftest` |
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
- `google_auth.py` depende de `settings` para leer rutas de credenciales.
- `countries.py` es independiente (no importa nada del proyecto).
- `data/` agrupa todos los archivos JSON: datos fake (`names.json`, `phones.json`) y credenciales de Google (`google_credentials.json`, etc.).
- Las credenciales están en `.gitignore`; no forman parte del código.
- `config/` no importa nada de `core/`, `automation/`, `sheets/` ni `web/` — es la capa más baja del sistema.
