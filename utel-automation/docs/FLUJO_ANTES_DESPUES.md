# Flujo de formularios — Antes vs Después

## ANTES: if/elif monolítico en FormFillerOrchestrator

```
                    FormFillerOrchestrator.fill()
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Navegar a LP       │
                    │  Preparar form      │
                    │  Detectar scope     │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  log_fields()       │
                    └─────────┬───────────┘
                              │
                    ┌─────────┴───────────┐
                    │                     │
                    ▼                     ▼
          ┌─────────────────┐   ┌──────────────────┐
          │ _mexico_         │   │ ELSE             │
          │ universidad?     │   │ _fill_standard() │
          │ YES              │   │                  │
          │                  │   │ SelectHandler    │
          │ _fill_           │   │ ContactFiller    │
          │ universidad()    │   │ PrivacyHandler   │
          │                  │   │ SubmissionVal.   │
          │ MexicoFormHandler│   └──────────────────┘
          │ Choices.js       │
          │ 4 fallback layers│
          └─────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  log_fields()       │
                    │  submit()           │
                    │  validate_post()    │
                    └─────────────────────┘

PROBLEMAS:
- Bandera _mexico_utel, _mexico_universidad
- _fill_standard() genérico para Mexico CMS y 14 países
- No hay lugar limpio para meter ColombiaCMS, PeruCMS, etc.
```

## DESPUÉS: Strategy + Registry

```
                    FormFillerOrchestrator.fill()
                              │
                              ▼
                    ┌─────────────────────┐
                    │  Navegar a LP       │
                    │  Preparar form      │
                    │  Detectar scope     │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  log_fields()       │
                    └─────────┬───────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  get_filler()       │  ← NUEVO
                    │  (Registry)         │
                    └─────────┬───────────┘
                              │
                    ┌─────────┴───────────┐
                    │                     │
                    ▼                     ▼
          ┌─────────────────┐   ┌──────────────────┐
          │ filler != None  │   │ filler == None   │
          │                 │   │ (país no migrado)│
          │ CmsFiller       │   │                  │
          │ .fill(ctx)      │   │ FALLBACK LEGACY  │
          │                 │   │                  │
          │ SelectHandler   │   │ if _mexico_      │
          │ ContactFiller   │   │   universidad:   │
          │ PrivacyHandler  │   │   _fill_uni()    │
          │ FormSubmitter   │   │ else:            │
          │ config-driven   │   │  _fill_standard()│
          └─────────────────┘   └──────────────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │  log_fields()       │
                    │  (o retorno directo)│
                    └─────────────────────┘

BENEFICIOS:
- Registry decide qué strategy usar (país + URL)
- CmsFiller es testeable aisladamente (9 tests)
- Nuevo país: crear strategy + entrada en CMS_CONFIGS
- Legacy intacto como fallback
- Sin nuevas banderas booleanas
```

## Mapa de archivos — Antes vs Después

```
ANTES:
automation/form/
├── form_filler_orch.py    ← 368 líneas, if/elif, 3 banderas
├── form_submitter.py      ← SUBMIT_BUTTONS hardcodeado
├── (demás componentes)
└── README.md

DESPUÉS:
automation/form/
├── form_filler_orch.py    ← +3 líneas (imports + bloque strategy)
├── form_submitter.py      ← +1 línea (parámetro submit_buttons opcional)
├── i_form_filler.py       ← NUEVO: Protocol
├── fill_context.py        ← NUEVO: Dataclass
├── registry.py            ← NUEVO: get_filler()
├── strategies/
│   ├── __init__.py        ← NUEVO: vacío
│   └── cms_filler.py      ← NUEVO: CmsFiller class
├── (demás componentes)    ← intactos
└── README.md

config/
├── form_configs.py        ← NUEVO: CmsConfig + CMS_CONFIGS dict

tests/unit/
├── test_cms_filler.py     ← NUEVO: 9 tests
├── (demás tests)          ← intactos
```

## Flujo de decisión de get_filler()

```
get_filler(country, landing_url, page, fake_data)
    │
    ├── ¿is_mexico_universidad_lp()?  →  None (usa legacy)
    │
    ├── ¿is_mexico_utel_lp() AND country.id in CMS_CONFIGS?  →  CmsFiller(config, ...)
    │
    └── else  →  None (usa legacy)
```
