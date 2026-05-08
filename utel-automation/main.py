# ============================================================
# main.py
# Punto de entrada de la aplicación FastAPI
# Define todas las rutas HTTP y el stream SSE
# Equivalente al @RestController + @SpringBootApplication en Spring Boot
# ============================================================

# ⚠️  FIX CRÍTICO PARA WINDOWS:
# En Windows, asyncio usa por defecto SelectorEventLoop que NO soporta
# subprocesos (subprocess) — y Playwright necesita subprocesos para lanzar Chromium.
# ProactorEventLoop sí soporta subprocesos en Windows.
# En Linux/Mac esto no es necesario.
import sys
import asyncio

if sys.platform == "win32":
    # Cambiamos el event loop a ProactorEventLoop ANTES de que arranque FastAPI
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


import asyncio                                  # Para tareas en background
from contextlib import asynccontextmanager      # Para el ciclo de vida de la app
from typing import Optional                     # Para tipos opcionales

from fastapi import FastAPI, BackgroundTasks, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles     # Para servir archivos CSS
from fastapi.templating import Jinja2Templates  # Para renderizar HTML
from loguru import logger                       # Para logs

from config.settings import settings            # Configuración del sistema
from config.models import RunRequest            # Modelo de la solicitud
from sheets.reader import SheetsReader          # Lee el Sheets
from sheets.writer import SheetsWriter          # Escribe en el Sheets
from automation.screenshot import ScreenshotManager  # Capturas y Drive
from events.queue import EventQueue             # Cola de eventos SSE
from orchestrator import Orchestrator           # Coordinador central


# ============================================================
# INICIALIZACIÓN DE SERVICIOS
# Equivalente a los @Bean de Spring Boot — se crean una sola vez
# ============================================================

# Cola de eventos global — conecta el Orchestrator con el stream SSE
event_queue = EventQueue()

# Instancias de los servicios — se crean una sola vez al iniciar
# Equivalente a @Autowired Singleton en Spring
sheets_reader = SheetsReader()
sheets_writer = SheetsWriter()
screenshot_manager = ScreenshotManager()

# Referencia al orchestrator activo (None si no hay proceso corriendo)
active_orchestrator: Optional[Orchestrator] = None


# ============================================================
# CICLO DE VIDA DE LA APLICACIÓN
# Equivalente a @PostConstruct y @PreDestroy en Spring Boot
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Define qué hacer al iniciar y al cerrar la aplicación.
    El código antes del 'yield' se ejecuta al arrancar.
    El código después del 'yield' se ejecuta al cerrar.
    """
    # Al iniciar: mostramos mensaje de bienvenida
    logger.info("🚀 UTEL Automation iniciado")
    logger.info(f"🌐 Interfaz disponible en: http://localhost:{settings.port}")

    yield  # La aplicación corre entre estos dos puntos

    # Al cerrar: limpiamos recursos
    logger.info("🔒 UTEL Automation cerrando...")


# ============================================================
# CREACIÓN DE LA APP FASTAPI
# Equivalente a @SpringBootApplication en Spring Boot
# ============================================================

app = FastAPI(
    title="UTEL Lead Tester",
    description="Sistema de automatización para testing de leads de UTEL",
    version="1.0.0",
    lifespan=lifespan
)

# Servimos los archivos estáticos (CSS) desde la carpeta /static
# Equivalente a configurar un ResourceHandler en Spring MVC
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuramos el motor de templates Jinja2 para renderizar HTML
# Equivalente a un ViewResolver en Spring MVC
templates = Jinja2Templates(directory="templates")


# ============================================================
# RUTAS HTTP — Equivalente a @GetMapping y @PostMapping en Spring
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Ruta principal — muestra la interfaz web.
    Equivalente a un @GetMapping("/") en Spring Boot.

    Renderiza el archivo templates/index.html con los países disponibles.
    """
    # Lista de países disponibles para el dropdown de la UI
    countries = [
        "Mexico", "Peru", "Colombia", "Ecuador", "Argentina",
        "Bolivia", "Chile", "USA", "Dominicana", "Paraguay",
        "Guatemala", "El Salvador", "Honduras", "Panama", "Global"
    ]

    # Renderizamos el template HTML pasando los datos necesarios
    # Equivalente a un ModelAndView en Spring MVC
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,       # FastAPI requiere siempre pasar el request
            "countries": countries,   # Lista de países para el dropdown
            "title": "UTEL Lead Tester"
        }
    )


@app.post("/api/run")
async def run_test(
    background_tasks: BackgroundTasks,  # Para ejecutar en background
    country: str = Form(...),           # País seleccionado en la UI
    sheet_id: str = Form(""),           # ID del Sheets (opcional)
    sheet_tab: str = Form(""),          # Hoja del Sheets (opcional)
):
    """
    Inicia el proceso de testing para un país.
    Equivalente a un @PostMapping("/api/run") en Spring Boot.

    El proceso corre en background para no bloquear la respuesta HTTP.
    La UI recibe actualizaciones en tiempo real via SSE (/api/stream).
    """
    global active_orchestrator, event_queue

    # Si hay un proceso activo, lo cancelamos primero
    if active_orchestrator:
        active_orchestrator.cancel()
        await asyncio.sleep(1)  # Pequeña pausa para que cancele

    # Reseteamos la cola de eventos para esta nueva ejecución
    event_queue.reset()

    # Creamos la solicitud de ejecución
    request = RunRequest(
        country=country,
        sheet_id=sheet_id if sheet_id else None,
        sheet_tab=sheet_tab if sheet_tab else None
    )

    # Creamos el Orchestrator con todas las dependencias inyectadas
    # Equivalente a @Autowired en Spring — le pasamos los servicios
    active_orchestrator = Orchestrator(
        sheets_reader=sheets_reader,
        sheets_writer=sheets_writer,
        screenshot_manager=screenshot_manager,
        event_queue=event_queue
    )

    logger.info(f"▶️  Iniciando proceso para {country}")

    # ⚠️  FIX WINDOWS: Ejecutamos Playwright en un thread separado con su propio event loop
    # background_tasks de FastAPI comparte el event loop de uvicorn
    # que en Windows NO puede lanzar subprocesos (Playwright los necesita)
    # La solución: correr el orchestrator en un ThreadPoolExecutor con loop propio
    import concurrent.futures
    import threading

    def run_in_new_loop():
        """Crea un event loop nuevo en un thread separado y corre el orchestrator"""
        # Creamos un event loop nuevo — completamente independiente del de FastAPI
        loop = asyncio.new_event_loop()
        # En Windows el loop nuevo también necesita ser ProactorEventLoop
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            # Corremos el orchestrator en este loop nuevo
            loop.run_until_complete(active_orchestrator.run(request))
        finally:
            loop.close()

    # Lanzamos el thread — FastAPI sigue respondiendo normalmente
    thread = threading.Thread(target=run_in_new_loop, daemon=True)
    thread.start()

    # Respondemos inmediatamente — el proceso corre en background
    return JSONResponse({
        "status": "started",
        "country": country,
        "message": f"Proceso iniciado para {country}"
    })


@app.get("/api/stream")
async def stream_events(request: Request):
    """
    Endpoint de Server-Sent Events (SSE).
    Mantiene una conexión abierta y envía eventos al browser en tiempo real.
    Equivalente a un WebSocket endpoint en Spring Boot.

    HTMX en el browser escucha este endpoint con hx-sse
    y actualiza la UI automáticamente cada vez que llega un evento.
    """
    logger.info("📡 Cliente SSE conectado")

    async def event_generator():
        """
        Generador que lee eventos de la cola y los envía al browser.
        Se ejecuta hasta que el proceso termina o el cliente se desconecta.
        """
        async for event in event_queue.consume():
            # Verificamos si el cliente sigue conectado
            if await request.is_disconnected():
                logger.info("📡 Cliente SSE desconectado")
                break
            yield event

    # StreamingResponse mantiene la conexión abierta
    # media_type="text/event-stream" es el tipo MIME para SSE
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            # Evitamos que el servidor o proxies cacheen el stream
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Necesario para que funcione en algunos navegadores
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/api/stop")
async def stop_process():
    """
    Cancela el proceso en curso.
    Se llama cuando el usuario presiona el botón "Detener" en la UI.
    Equivalente a un @PostMapping("/api/stop") en Spring Boot.
    """
    global active_orchestrator

    if active_orchestrator:
        active_orchestrator.cancel()
        logger.info("🛑 Proceso cancelado por el usuario")
        return JSONResponse({
            "status": "stopped",
            "message": "Proceso cancelado"
        })

    return JSONResponse({
        "status": "no_process",
        "message": "No hay proceso activo"
    })


@app.get("/api/status")
async def get_status():
    """
    Retorna el estado actual del sistema.
    Útil para verificar si hay un proceso corriendo.
    Equivalente a un @GetMapping("/api/status") en Spring Boot.
    """
    is_running = active_orchestrator is not None and not event_queue._finished

    return JSONResponse({
        "running": is_running,
        "message": "Proceso en curso" if is_running else "Sin proceso activo"
    })


@app.get("/api/countries")
async def get_countries():
    """
    Retorna la lista de países disponibles en formato JSON.
    Útil si se quiere consumir desde Postman o desde otra aplicación.
    """
    countries = [
        "Mexico", "Peru", "Colombia", "Ecuador", "Argentina",
        "Bolivia", "Chile", "USA", "Dominicana", "Paraguay",
        "Guatemala", "El Salvador", "Honduras", "Panama", "Global"
    ]
    return JSONResponse({"countries": countries})


# ============================================================
# PUNTO DE ENTRADA — Para correr desde terminal con: python main.py
# Equivalente a public static void main() en Java
# ============================================================

if __name__ == "__main__":
    import uvicorn

    # Iniciamos el servidor con uvicorn
    # reload=True hace que el servidor se reinicie automáticamente
    # cuando cambias el código — útil durante desarrollo
    uvicorn.run(
        "main:app",           # Nombre del módulo y la instancia de FastAPI
        host="0.0.0.0",       # Escucha en todas las interfaces de red
        port=settings.port,   # Puerto del .env (por defecto 8000)
        reload=True,          # Reinicio automático al cambiar código
        log_level="info"      # Nivel de logs del servidor
    )