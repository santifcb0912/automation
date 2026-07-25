# Contracts — Interfaces y DTOs del sistema de formularios

Define los contratos que conectan el `engine/` (orquestador) con las `fillers/` (strategies concretas).
Es el único paquete del que dependen tanto engine como fillers. Sin esto, no hay comunicación posible.

## Scripts

### `i_form_filler.py`
**IFormFiller** — Interfaz (Protocol) que toda strategy de llenado debe implementar.

```python
class IFormFiller(Protocol):
    async def fill(self, ctx: FillContext) -> Optional[str]: ...
```

- `Protocol` de typing → tipado estructural. Cualquier clase con un `fill()` que coincida en firma es un `IFormFiller`, sin necesidad de herencia explícita.
- `fill(ctx)` → recibe un `FillContext` con los datos del lead. Retorna `None` si tuvo éxito, o un `str` con la razón del error.
- Es la interfaz más pequeña posible (1 solo método) — cumple Interface Segregation Principle.

### `fill_context.py`
**FillContext** — Dataclass que encapsula todos los parámetros que la strategy necesita.

```python
@dataclass
class FillContext:
    form_scope: Locator    # Contenedor del formulario en el DOM
    level: str             # Nivel canónico (Maestria, Licenciatura...)
    raw_level: str         # Nivel original desde Sheets
    test_email: str        # Email de prueba del lead
    fake_name: str         # Nombre ficticio generado
    fake_phone: str        # Teléfono ficticio generado según país
```

- Es un `@dataclass` → Python genera `__init__`, `__repr__`, `__eq__` automáticamente.
- Sin este DTO, las strategies tendrían firmas hinchadas con 6+ parámetros.
- Si mañana se necesita pasar `utm_source` o `lead_id`, solo se agrega un campo aquí — ni la interfaz ni los callers cambian.

## Diagrama de flujo

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    PAQUETE contracts/                                        │
│                                                                              │
│  ┌──────────────────────────────────────┐   ┌────────────────────────────┐  │
│  │         IFormFiller (Protocol)       │   │      FillContext           │  │
│  │                                      │   │      ───────────           │  │
│  │  define el CONTRATO que toda         │   │                            │  │
│  │  strategy debe cumplir               │   │  Transporta los datos      │  │
│  │                                      │   │  del lead desde el         │  │
│  │  ┌─────────────────────────────────┐ │   │  orquestador hacia la      │  │
│  │  │ async def fill(self,           │ │   │  strategy concreta:        │  │
│  │  │     ctx: FillContext           │ │   │                            │  │
│  │  │ ) -> Optional[str]             │ │   │  • form_scope (Locator)    │  │
│  │  └─────────────────────────────────┘ │   │  • level (str)            │  │
│  │                                      │   │  • raw_level (str)        │  │
│  │  None  = éxito                       │   │  • test_email (str)       │  │
│  │  str   = razón del error             │   │  • fake_name (str)        │  │
│  │                                      │   │  • fake_phone (str)       │  │
│  └──────────────┬───────────────────────┘   └────────────┬───────────────┘  │
│                 │                                        │                  │
│                 └────────────┬───────────────────────────┘                  │
│                              │                                              │
│    ┌─────────────────────────┴─────────────────────────────┐                │
│    │                   SE CONECTAN ASÍ:                    │                │
│    │                                                       │                │
│    │  engine/registry.py         engine/orchestrator.py    │                │
│    │  ────────────────────       ──────────────────────    │                │
│    │  importa IFormFiller        importa FillContext       │                │
│    │  y retorna una strategy     y crea la instancia       │                │
│    │  que implementa el          con los datos del lead:   │                │
│    │  Protocol:                                           │                │
│    │                              ctx = FillContext(       │                │
│    │  def get_filler(...          form_scope=scope,        │                │
│    │  ) -> IFormFiller:           level=level,             │                │
│    │      return MexicoCms-       raw_level=...,           │                │
│    │             Filler(...)      test_email=...,          │                │
│    │                              fake_name=...,           │                │
│    │                              fake_phone=...,          │                │
│    │  fillers/ implementan        )                        │                │
│    │  IFormFiller:                                        │                │
│    │                              error = await           │                │
│    │  class MexicoCmsFiller(           filler.fill(ctx)   │                │
│    │    IFormFiller):                                     │                │
│    └──────────────────────────────────────────────────────┘                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                      FLUJO COMPLETO (simplificado)                          │
│                                                                              │
│  engine/orchestrator.py                                                      │
│       │                                                                      │
│       │ 1. Obtiene strategy vía registry.py                                  │
│       │     filler = get_filler(country, url, page, fake)                    │
│       │                           ↓                                         │
│       │               registry devuelve MexicoCmsFiller                      │
│       │               (que implementa IFormFiller)                           │
│       │                                                                      │
│       │ 2. Crea FillContext con datos del lead                               │
│       │     ctx = FillContext(form_scope=..., level=..., etc.)               │
│       │                                                                      │
│       │ 3. Ejecuta la strategy                                               │
│       │     error = await filler.fill(ctx)                                   │
│       │                           ↓                                         │
│       │               MexicoCmsFiller recibe ctx                             │
│       │               y usa los datos para llenar el form                    │
│       │                                                                      │
│       │ 4. Retorna resultado                                                 │
│       │     return error  # None = ok, str = fallo                          │
│       │                                                                      │
└──────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════

               ¿QUÉ PASA SI NO EXISTIERAN ESTOS CONTRATOS?

Sin IFormFiller y FillContext:

┌──────────────────────────────────────────────────────────────────────────────┐
│  engine/orchestrator.py tendría que hacer:                                   │
│                                                                              │
│  if country.id == "mexico":                                                  │
│      error = await MexicoCmsFiller(config, page, country, fake)              │
│          .fill(scope, level, raw_level, email, name, phone)                  │
│  elif country.id == "colombia":                                              │
│      error = await ColombiaCmsFiller(config, page, country, fake)            │
│          .fill(scope, level, raw_level, email, name, phone)                  │
│  elif ...                                                                    │
│                                                                              │
│  ❌ Violación Open/Closed: cada nuevo país → modificar orquestador          │
│  ❌ Firma hinchada: 6+ parámetros en fill()                                 │
│  ❌ Sin polimorfismo: no se puede iterar ni inyectar mocks                   │
│  ❌ Sin encapsulación: cambiar un parámetro = cambiar N archivos             │
└──────────────────────────────────────────────────────────────────────────────┘

   Con contratos → 3 líneas, sin if, sin imports de fillers concretos.
```
