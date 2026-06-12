# UTEL Automation

Automatización E2E de testing de leads: llena formularios en landing pages, busca los leads en el CRM InConcert, toma capturas de pantalla y registra resultados en Google Sheets.

---

## Cómo empezar

```bash
# 1. Clonar / copiar el proyecto
# 2. Crear y activar entorno virtual
python -m venv venv
.\venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt
playwright install chromium

# 4. Configurar variables de entorno
#    Copiar .env.example a .env y llenar credenciales

# 5. Iniciar servidor
python main.py
#   o bien:
#   uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 6. Abrir http://localhost:8000 en el navegador
```

> **Si el proyecto fue creado con otra cuenta de Windows y da "acceso denegado":**
> Abrir PowerShell **como Administrador** en la carpeta del proyecto y ejecutar:
> ```powershell
> takeown /F . /R /D S
> icacls . /reset /T /Q
> icacls . /grant "$env:USERNAME:(OI)(CI)F" /T /Q
> ```
> Esto transfiere la propiedad al usuario actual y resetea los permisos.

---

## Arquitectura

```
web/ (FastAPI)
  └── routes.py          → POST /api/run, GET /api/stream (SSE)
      └── Orchestrator   → hilo separado, event loop propio
          │
          ├── SheetsReader        (lee leads de Google Sheets)
          ├── FormFillerOrch      (abre LP, llena y envía formulario)
          │   ├── FormDetector         (detecta tipo/scope del form)
          │   ├── SelectHandler        (selects: modalidad, área, programa)
          │   ├── ProgramSearchEngine  (buscador de programas)
          │   ├── ContactFieldFiller   (nombre, email, teléfono)
          │   ├── PrivacyHandler       (checkbox de privacidad)
          │   └── FormSubmitter        (click submit + validación)
          ├── InConcertClient    (busca lead en CRM)
          │   ├── InConcertAuth       (login)
          │   ├── InConcertSearch     (search + acciones + expansión)
          │   └── LeadDetailOpener    (3-puntos → Gestionar)
          ├── ScreenshotManager  (captura PNG + sube a Google Drive)
          └── SheetsWriter      (escribe link/error en Sheets)
```

### Capas

| Capa | Directorio | Responsabilidad |
|------|-----------|----------------|
| **Web** | `web/` | FastAPI, rutas, SSE, DI |
| **Coordinación** | `orchestrator.py` | Pipeline por lead |
| **Automatización** | `automation/` | Playwright: forms, CRM, screenshots |
| **Configuración** | `config/` | Países, settings, data (names/phones) |
| **Core** | `core/` | Enums, modelos, interfaces, fake data |
| **Sheets** | `sheets/` | Lectura/escritura Google Sheets |
| **Eventos** | `events/` | SSE thread-safe bridge |
| **Tests** | `tests/` | Unit tests con MockPage |

### Flujo por lead (diagrama)

```
         ┌─────────────────────────────┐
         │  POST /api/run (FastAPI)     │
         │  → Orchestrator.run()        │
         └─────────────┬───────────────┘
                       │
         ┌─────────────▼───────────────┐
         │ SheetsReader.get_leads()     │
         │ → List[LeadRow]             │
         └─────────────┬───────────────┘
                       │
         ┌─────────────▼───────────────┐
         │ Por cada LeadRow:           │
         │                             │
         │  ┌───────────────────────┐  │
         │  │ BrowserManager.launch()│  │
         │  │ → new_page()          │  │
         │  └──────────┬────────────┘  │
         │             │               │
         │  ┌──────────▼────────────┐  │
         │  │ FormFillerOrch.fill() │  │
         │  │ 1. goto(LP)          │  │
         │  │ 2. Detectar tipo     │  │
         │  │ 3. Scroll a form     │  │
         │  │ 4. Seleccionar       │  │
         │  │    modalidad/área/   │  │
         │  │    programa          │  │
         │  │ 5. Llenar nombre,    │  │
         │  │    email, teléfono   │  │
         │  │ 6. Check privacidad  │  │
         │  │ 7. Click submit      │  │
         │  └──────────┬────────────┘  │
         │             │               │
         │  ┌──────────▼────────────┐  │
         │  │ InConcertClient:      │  │
         │  │ 1. auth.login()      │  │
         │  │ 2. search.search()   │  │
         │  │ 3. detail.open()     │  │
         │  │ 4. expand_creation() │  │
         │  │ 5. expand_contact()  │  │
         │  └──────────┬────────────┘  │
         │             │               │
         │  ┌──────────▼────────────┐  │
         │  │ ScreenshotManager     │  │
         │  │ .take_and_upload()    │  │
         │  │ → link de Drive      │  │
         │  └──────────┬────────────┘  │
         │             │               │
         │  ┌──────────▼────────────┐  │
         │  │ SheetsWriter          │  │
         │  │ .write_success()      │  │
         │  │ → celda {col}{row}    │  │
         │  └───────────────────────┘  │
         │                             │
         └─────────────┬───────────────┘
                       │
         ┌─────────────▼───────────────┐
         │ BrowserManager.close()      │
         │ EventQueue → SSE → UI      │
         └─────────────────────────────┘

         Si falla en cualquier paso:
         → SheetsWriter.write_error()
         → logger.error()
         → SSE "lead_error"
```

---

## Principios y Reglas

### SOLID

| Principio | Cómo se aplica |
|-----------|---------------|
| **SRP** | Cada clase tiene una responsabilidad única. `FormFillerOrch` orquesta, no llena campos. `ContactFieldFiller` solo llena nombre/email/tel. `Country` es un dataclass puro sin lógica de generación. |
| **OCP** | `FakeDataService` recibe `INameProvider` y `IPhoneProvider` por DI. Agregar un nuevo provider (ej: `RandomEmailProvider`) no modifica nada existente. |
| **LSP** | Los providers implementan `Protocol`s. Cualquier clase que cumpla el Protocol puede reemplazar al provider sin cambiar el resto del sistema. |
| **ISP** | Interfaces pequeñas y específicas: `INameProvider` (1 método), `IPhoneProvider` (1 método). No hay interfaces enormes con métodos que no se usan. |
| **DIP** | `FormFillerOrch` depende de `FakeDataService` (abstracción, no concreto). `Orchestrator` depende de `IEventPublisher`, `ILeadRepository`, `IScreenshotService`. Los módulos de alto nivel no importan módulos de bajo nivel. |

### POO

- **Dataclasses como DTOs**: `Country`, `LeadRow`, `RunRequest`, `RunResult` — solo datos, sin lógica.
- **Composición sobre herencia**: `InConcertClient` compone `InConcertAuth`, `InConcertSearch`, `LeadDetailOpener`. No hay jerarquías de herencia.
- **Inyección de dependencias**: Las dependencias se pasan por constructor, no se crean internamente.
- **Protocols como interfaces**: `INameProvider`, `IPhoneProvider`, `IEventPublisher` — duck typing con tipado estático.

### Métodos lineales y secuenciales

- **Sin anidamiento innecesario**: Cada método hace una sola cosa y tiene un nivel de indentación.
- **Early return**: Si algo falla, se retorna `False`/`None` inmediatamente. No hay cadenas de `if/else`.
- **Try/except en el lugar correcto**: Cada método captura sus propias excepciones y las traduce a un valor de retorno booleano.
- **Secuencia clara**: El código se lee de arriba a abajo como una receta. Ejemplo en `expand_contact_section`: `wait_for → scroll_into_view → click → wait_for → scroll_into_view`.
- **Máximo un nivel de anidamiento**: Excepciones contadas cuando realmente es necesario (ej: reintentos con contador).

### Inyección de Dependencias

Las dependencias se pasan por constructor, nunca se crean con `new` dentro del método:

```python
# Bien
class FormFillerOrchestrator:
    def __init__(self, page: Page, country: Country, fake_data_service: FakeDataService):
        ...

# Mal
class FormFillerOrchestrator:
    def __init__(self, page: Page, country: Country):
        self._fake_data = FakeDataService(RandomNameProvider(), RandomPhoneProvider())
```

El `Orchestrator` central crea e inyecta todas las dependencias en el punto de entrada.

### Playwright: selectores semánticos

**Regla fija**: No usar coordenadas (`page.mouse.click`, `bounding_box`), no usar `page.evaluate()` para hacer clics. Usar los selectores semánticos de Playwright:

| Prioridad | Selector | Uso |
|-----------|----------|-----|
| 1 | `get_by_role("link", name="Email")` | Elementos con rol ARIA |
| 2 | `get_by_text("Contacto", exact=True)` | Texto visible exacto |
| 3 | `locator("div.timeline-title").filter(has_text="Creación")` | Filtro por texto + tag/clase |
| 4 | `locator("button").filter(has=locator("span[class*='ellipsis']"))` | Botón que contiene un icono específico |
| 5 | `locator("a.dropdown-item[title='Gestionar"]` | Selector CSS cuando no hay ARIA |
| 6 | `get_by_placeholder("Ingrese un texto para buscar")` | Por placeholder en inputs |

- Siempre usar `scroll_into_view_if_needed()` antes de clickear.
- Usar `wait_for(state="visible")` con timeout explícito.
- `force=True` solo como último recurso cuando el elemento no es actionable.
- Preferir `filter(has_text=...)` sobre `:has-text()` (no soportado en todos los contextos).
- No usar `:visible` (pseudo-selector no soportado por Playwright).

**Excepción documentada (deuda técnica)**: El `LeadDetailOpener` en `lead_detail.py` usa coordenadas y `page.evaluate` para abrir el menú de 3 puntos, porque el frontend de InConcert no tiene atributos ARIA ni selectores semánticos estables. Esto está identificado como deuda técnica para refactorizar cuando el equipo de InConcert agregue atributos accesibles.

---

## Estructura de Métodos

Cada método público sigue este patrón:

```python
async def metodo(self, ...) -> bool:
    try:
        # 1. Esperar que el elemento esté visible
        await elemento.wait_for(state="visible", timeout=X)

        # 2. Scroll si es necesario
        await elemento.scroll_into_view_if_needed(timeout=Y)

        # 3. Pausa humana
        await BrowserManager.human_delay(200, 400)

        # 4. Acción
        await elemento.click(timeout=5000)
        await BrowserManager.human_delay(500, 800)

        # 5. Verificar resultado
        await resultado.wait_for(state="visible", timeout=X)

        logger.info("Éxito: ...")
        return True

    except TimeoutError:
        logger.error("Timeout: ...")
        return False
    except Exception as e:
        logger.error(f"Error: {e}")
        return False
```

---

## Configuración de Países

Cada `Country` en `config/countries.py` define:

- `id`: identificador único (ej: "mexico")
- `sheet_names`: nombres que puede tener en Google Sheets
- `inconcert_url`: URL del CRM
- `fake_name` / `fake_phone`: valores por defecto (fallback)
- `phone_prefix`: código de país (+52, +51, etc.)
- `level_equivalences`: mapeo de niveles para países específicos (Chile: Maestría → Magister)

Los datos aleatorios viven en `config/data/`:
- `names.json`: 15-30 nombres por país
- `phones.json`: templates con sintaxis `(opción1|opción2)########`

---

## Para otros desarrolladores

### Stack técnico

- **Python 3.11+** — async/await en toda la automatización
- **Playwright** — motor de navegador (Chromium headless=false)
- **FastAPI** — servidor web + SSE
- **Google Sheets API** (gspread) — leer/escribir leads
- **Google Drive API** — subir screenshots
- **Pydantic** — settings con tipado desde .env

### Lo que debe saber antes de tocar el código

1. **Dos event loops**: FastAPI corre en un event loop, `Orchestrator` corre en otro hilo con su propio loop. No compartir objetos asyncio entre ellos. Usar `queue.Queue` (thread-safe) para comunicación.

2. **El navegador es una ventana real** (`headless=False`). No cerrarla manualmente. `BrowserManager.close()` se encarga en el `finally` de cada lead.

3. **Human delays**: `BrowserManager.human_delay(min_ms, max_ms)` después de cada acción importante. Esto simula comportamiento humano y evita detección por Cloudflare.

4. **Logging**: `loguru` con `logger.info/success/warning/error`. No usar `print()`. Los logs son la única forma de debuggear.

5. **Tests**: Usar `MockPage` que simula Playwright sin abrir un navegador. `pytest-asyncio` para tests async. No hay tests de integración (requieren navegador real y credenciales).

6. **Timeouts**: Cada `wait_for` tiene timeout explícito. No confiar en timeouts por defecto. Si un método falla por timeout, aumentar el timeout antes de cambiar la lógica.

7. **México tiene dos flujos**: `cms` (utel.edu.mx) y `universidad` (universidad.utel.edu.mx). Se detectan por URL y cambian el comportamiento del form filler.

8. **No modificar `lead_detail.py` sin refactorizar**: Es la única clase que aún usa coordenadas y `page.evaluate`. Cualquier cambio debe eliminar esa deuda técnica.

9. **Agregar un país nuevo**: Crear entrada en `COUNTRIES` en `config/countries.py`, agregar nombres en `config/data/names.json` y template en `config/data/phones.json`, agregar a `COUNTRY_OPTIONS` en `web/routes.py`.

10. **Debugging de selectores**: Si un selector no encuentra un elemento, primero verificar con `page.pause()` (modo inspector) o agregar un `logger.info` con `await page.content()` antes del `wait_for`. No asumir que el selector es incorrecto — a veces el elemento no ha cargado.
