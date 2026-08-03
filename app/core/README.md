# Core Package — Diagrama de flujo

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐        
│                                   EXTERNO AL PAQUETE                                      │       
│                                                                                           │       
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────┐  ┌──────────────┐   │       
│  │  Orchestrator     │  │  web/routes.py   │  │  events/queue.py     │  │  config/     │   │      
│  │  orchestrator.py  │  │  /api/run        │  │  EventQueue          │  │  data/       │   │      
│  └────────┬──────────┘  └────────┬─────────┘  └──────────┬───────────┘  │  names.json  │   │      
│           │                      │                       │              │  phones.json │   │      
│           │                      │                       │              └──────┬───────┘   │      
│           │                      │                       │                     │           │      
│  ┌────────▼──────────────────────▼───────────────────────▼─────────────────────▼────────┐  │      
│  │                                                                                       │  │     
│  │                                    core/                                              │  │     
│  │                                                                                       │  │     
│  │  ┌────────────────────────────────────────────────────────────────────────────────┐  │  │      
│  │  │  models.py — DTOs del sistema                                                   │  │  │     
│  │  │                                                                                 │  │  │     
│  │  │  LeadRow                    RunRequest                                          │  │  │     
│  │  │  ├─ row_number             ├─ country                                           │  │  │     
│  │  │  ├─ country_name           ├─ sheet_id   (opcional, default None)              │  │  │      
│  │  │  ├─ nivel                  ├─ sheet_tab  (opcional, default None)              │  │  │      
│  │  │  ├─ landing_url            └─ flow       (cms/universidad, opcional)           │  │  │      
│  │  │  ├─ form_type                                                                    │  │  │    
│  │  │  ├─ cliente                                                                      │  │  │    
│  │  │  └─ test_email (default "")                                                      │  │  │    
│  │  └────────────────┬───────────────────────────────────────────────────────────────┘  │  │      
│  │                   │                                                                    │  │    
│  │  ┌────────────────▼───────────────────────────────────────────────────────────────┐  │  │      
│  │  │  exceptions.py — Excepciones del dominio                                        │  │  │     
│  │  │                                                                                 │  │  │     
│  │  │  CountryNotFoundError(ValueError)     → pipeline/orchestrator.py                │  │  │     
│  │  │  BrowserNotReadyError(RuntimeError)   → automation/browser.py                   │  │  │     
│  │  │  GoogleAuthError(RuntimeError)        → config/google_auth.py                   │  │  │     
│  │  └────────────────────────────────────────────────────────────────────────────────┘  │  │      
│  │                                                                                       │  │     
│  │  ┌────────────────────────────────────────────────────────────────────────────────┐  │  │      
│  │  │  interfaces/i_event_publisher.py — Protocol para SSE                            │  │  │     
│  │  │                                                                                 │  │  │     
│  │  │  IEventPublisher(Protocol)                                                      │  │  │     
│  │  │  ├─ emit(event_type, data)          → Orchestrator llama                        │  │  │     
│  │  │  ├─ mark_finished()                 → Orchestrator al terminar                  │  │  │     
│  │  │  ├─ reset()                         → routes.py antes de empezar                │  │  │     
│  │  │  ├─ is_finished → bool              → routes.py para SSE 410                   │  │  │      
│  │  │  └─ consume() → AsyncGenerator      → sse_handler.py envia al frontend          │  │  │     
│  │  │                                                                                 │  │  │     
│  │  │  Implementado por: events/queue.py → EventQueue                                │  │  │      
│  │  └────────────────────────────────────────────────────────────────────────────────┘  │  │      
│  │                                                                                       │  │     
│  │  ┌────────────────────────────────────────────────────────────────────────────────┐  │  │      
│  │  │  fake_data/ — Datos de prueba por país                                          │  │  │     
│  │  │                                                                                 │  │  │     
│  │  │  interfaces.py                            providers.py                          │  │  │     
│  │  │  ┌──────────────────────────┐            ┌──────────────────────────┐           │  │  │     
│  │  │  │ INameProvider(Protocol)  │            │ RandomNameProvider       │           │  │  │     
│  │  │  │  └─ get_name() → str     │◄───implementa───└─ get_name() → str        │           │  │  │
│  │  │  └──────────────────────────┘            │  └─ _ensure_loaded()      │           │  │  │    
│  │  │  ┌──────────────────────────┐            └──────────────────────────┘           │  │  │     
│  │  │  │ IPhoneProvider(Protocol) │            ┌──────────────────────────┐           │  │  │     
│  │  │  │  └─ get_phone(country)   │◄───implementa───┤ RandomPhoneProvider      │           │  │  │
│  │  │  └──────────────────────────┘            │  ├─ get_phone(country)    │           │  │  │    
│  │  │                                         │  ├─ _ensure_loaded()      │           │  │  │     
│  │  │                                         │  └─ _generate_from_       │           │  │  │     
│  │  │                                         │      _template()          │           │  │  │     
│  │  │                                         └──────────────────────────┘           │  │  │      
│  │  │                                                                                 │  │  │     
│  │  │  service.py                                                                     │  │  │     
│  │  │  ┌─────────────────────────────────────────────────────────────────────────┐    │  │  │     
│  │  │  │ FakeDataService (Facade)                                                 │    │  │  │    
│  │  │  │  ├─ __init__(name_provider, phone_provider)  ← Constructor Injection    │    │  │  │     
│  │  │  │  ├─ get_name()                              → delega a INameProvider    │    │  │  │     
│  │  │  │  └─ get_phone(country_id)                   → delega a IPhoneProvider   │    │  │  │     
│  │  │  └─────────────────────────────────────────────────────────────────────────┘    │  │  │     
│  │  └────────────────────────────────────────────────────────────────────────────────┘  │  │      
│  │                                                                                       │  │     
│  │  ┌────────────────────────────────────────────────────────────────────────────────┐  │  │      
│  │  │  utils.py — Utilidades generales                                               │  │  │      
│  │  │                                                                                 │  │  │     
│  │  │  human_delay(min_ms, max_ms)     → espera aleatoria para simular humano         │  │  │     
│  │  │                                     (anti-deteccion Cloudflare)                 │  │  │     
│  │  │                                                                                 │  │  │     
│  │  │  Usado por: inconcert_client, search, auth (paquete InConcert)                  │  │  │     
│  │  └────────────────────────────────────────────────────────────────────────────────┘  │  │      
│  │                                                                                       │  │     
│  └───────────────────────────────────────────────────────────────────────────────────────┘  │     
│                                     │                                                       │     
│           ┌─────────────────────────┼─────────────────────────┐                             │     
│           │                         │                         │                             │     
│           ▼                         ▼                         ▼                             │     
│  ┌──────────────────┐  ┌───────────────────────┐  ┌──────────────────────┐                  │     
│  │  Orchestrator     │  │  events/queue.py      │  │  form/engine/        │                  │    
│  │  Crea RunRequest  │  │  Implementa            │  │  orchestrator.py     │                  │   
│  │  Recibe LeadRow   │  │  IEventPublisher       │  │  (FormFillerOrches-  │                  │   
│  │  Usa FakeData     │  │                       │  │  trator)             │                  │    
│  │  Service          │  │                       │  │  Usa FakeDataService │                  │    
│  │                   │  │                       │  │  .get_name()         │                  │    
│  └──────────────────┘  └───────────────────────┘  │  .get_phone()         │                  │    
│                                                    └──────────────────────┘                  │    
│                                                                                             │     
│  Conexiones externas:                                                                        │    
│  ┌────────────────┬────────────────────────────────────────────────────────────┐           │      
│  │ Componente     │ Lo usa core para...                                        │           │      
│  ├────────────────┼────────────────────────────────────────────────────────────┤           │      
│  │ config/data/   │ names.json y phones.json — datos de prueba por país        │           │      
│  │ config/        │ No depende directamente de settings.py                     │           │      
│  │ {todos}        │ Todos los paquetes importan de core/, core no importa      │           │      
│  │                │ de nadie dentro del proyecto (regla de dependencia)        │           │      
│  └────────────────┴────────────────────────────────────────────────────────────┘           │      
└──────────────────────────────────────────────────────────────────────────────────────────────┘    
```

## Regla fundamental de core/

**`core/` no importa ningún otro módulo del proyecto.** Es la capa cero:

```
  web/  sheets/  automation/  events/                     
     \      |        |        /                           
      \     |        |       /                            
       \    |        |      /                             
        \   |        |     /                              
         ┌─┴────────┴────┐                                
         │     core      │  ← No importa nada del proyecto
         └───────────────┘                                
                 │                                        
         config/ (data externa)                           
```
