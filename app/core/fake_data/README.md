# core/fake_data — Diagrama de flujo

```
                            ┌─────────────────────────────────────┐ 
                            │            Caller externo            │
                            │ (form/engine/orchestrator.py         │
                            │  → FormFillerOrchestrator,           │
                            │  pipeline/orchestrator, etc)         │
                            └──────────┬──────────────────────────┘ 
                                       │                            
                          ┌────────────┴────────────┐               
                          │  get_name()             │               
                          │  get_phone(country_id)  │               
                          └────────────┬────────────┘               
                                       │                            
                                       ▼                            
                    ┌───────────────────────────────────┐           
                    │         FakeDataService            │          
                    │           (Facade)                 │          
                    │                                    │          
                    │  Recibe INameProvider e            │          
                    │  IPhoneProvider por constructor    │          
                    └──────┬──────────────────┬──────────┘          
                           │                  │                     
                           ▼                  ▼                     
            ┌──────────────────────┐  ┌──────────────────────────┐  
            │    INameProvider     │  │    IPhoneProvider         │ 
            │      (Protocol)      │  │      (Protocol)           │ 
            │  get_name() → str    │  │  get_phone(cid) → str     │ 
            └──────────┬───────────┘  └────────────┬─────────────┘  
                       │                            │               
                       │ implementa                 │ implementa    
                       ▼                            ▼               
            ┌──────────────────────┐  ┌──────────────────────────┐  
            │  RandomNameProvider  │  │  RandomPhoneProvider      │ 
            │                      │  │                           │ 
            │  _ensure_loaded()    │  │  _ensure_loaded()         │ 
            │    ↓                 │  │    ↓                      │ 
            │  json.load → list    │  │  json.load → dict[cid]    │ 
            │    ↓                 │  │    ↓                      │ 
            │  random.choice()     │  │  _generate_from_template  │ 
            │    ↓                 │  │    ↓                      │ 
            │  return str          │  │  return str               │ 
            └──────┬───────────────┘  └────────────┬──────────────┘ 
                   │                               │                
                   │  lee                           │  lee          
                   ▼                               ▼                
      ┌───────────────────────┐      ┌──────────────────────────┐   
      │  config/data/         │      │  config/data/             │  
      │  names.json           │      │  phones.json              │  
      │                       │      │  {"mx": "(55|56)########",│  
      │  ["Juan Pérez",       │      │   "co": "3##########",    │  
      │   "María García",     │      │   ...}                    │  
      │   ... 20 nombres]     │      └──────────────────────────┘   
      └───────────────────────┘                                     
```

## Flujo de datos

```
get_name()                                                      
  └─ FakeDataService.get_name()                                 
      └─ RandomNameProvider.get_name()                          
          └─ _ensure_loaded() ──→ names.json ──→ list[str]      
          └─ random.choice(list) ──→ str                        
                                                                
get_phone(country_id)                                           
  └─ FakeDataService.get_phone(country_id)                      
      └─ RandomPhoneProvider.get_phone(country_id)              
          └─ _ensure_loaded() ──→ phones.json ──→ dict[str, str]
          └─ template = dict[country_id]                        
          └─ _generate_from_template(template) ──→ str          
```

## Responsabilidades

| Componente | Rol |
|---|---|
| `FakeDataService` | Fachada; recibe providers por constructor injection |
| `INameProvider` | Protocolo: `get_name() -> str` (sin país — pool global) |
| `IPhoneProvider` | Protocolo: `get_phone(country_id) -> str` (formato local) |
| `RandomNameProvider` | Carga lista plana desde JSON; elige al azar |
| `RandomPhoneProvider` | Carga plantillas por país desde JSON; genera número |
| `names.json` | 20 nombres compartidos por todos los países |
| `phones.json` | Plantillas de formato telefónico por país |

## Notas

- `RandomNameProvider` ignora el país — todos los leads usan la misma pool de 20 nombres.
- `RandomPhoneProvider` sí depende del país — cada país tiene su propio formato telefónico.
- Ambos providers hacen lazy loading del JSON en la primera llamada (`_ensure_loaded`).
- Si el archivo JSON no existe o está corrupto, retornan `""` silenciosamente.
- No hay fallbacks ni herencia entre providers — cada uno es independiente.
