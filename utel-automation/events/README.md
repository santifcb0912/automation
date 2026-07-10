# events/ — Diagrama de flujo


```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  LO QUE SE VE EN EL NAVEGADOR          LO QUE PASA ADENTRO   │
│                                                             │
│  ┌──────────────────────┐          ┌──────────────────────┐ │
│  │                      │          │                      │ │
│  │  ● Iniciando...      │          │  Llenando formulario │ │
│  │  ● 5 leads listos    │   ◄───  │  Buscando en CRM...  │ │
│  │  ● Procesando 1/5    │          │  Tomando captura...  │ │
│  │  ● Lead 1 listo ✓    │          │  Subiendo a Drive... │ │
│  │  ● Procesando 2/5    │          │  Guardando en Sheets │ │
│  │  ● ...               │          │  ...                 │ │
│  │                      │          │                      │ │
│  └──────────────────────┘          └──────────────────────┘ │
│           ▲                                │                │
│           │           EventQueue            │                │
│           └───────────────┬─────────────────┘                │
│                           │                                  │
│              ┌────────────┴────────────┐                     │
│              │    Buzón de mensajes    │                     │
│              │                         │                     │
│              │  "empezamos"            │                     │
│              │  "encontramos N leads"  │                     │
│              │  "procesando lead 1"    │                     │
│              │  "lead 1 listo"         │                     │
│              │  ...                    │                     │
│              └────────────────────────┘                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## ¿Qué hace cada pieza?

| Pieza | ¿Qué hace? |
|---|---|
| `EventQueue` | Es una **bandeja de mensajes**. Una parte deja mensajes y la otra los recoge |
| `emit()` | Dejar un mensaje en la bandeja (ej: "empezamos", "todo listo") |
| `consume()` | Recoger mensajes de la bandeja y pasarlos al navegador |
| `reset()` | Vaciar la bandeja para empezar de nuevo |
| `mark_finished()` | Poner un cartel de "TERMINADO" para que el navegador sepa que ya no vienen más mensajes |
| `is_finished` | Revisar si el cartel de "TERMINADO" está puesto |

## Así se ve en pantalla

Cuando el usuario hace clic en "Iniciar", pasa esto:

```
Usuario hace clic en "Iniciar"
        │
        ▼
Se vacía la bandeja (por si quedaron mensajes viejos)
Se arranca el proceso pesado en segundo plano
        │
        ▼
El navegador abre una conexión SSE (canal de escucha)
        │
        ▼ ──────────────────────────────────────────────────
          El proceso pesado empieza a enviar mensajes:

  ┌─────────┬──────────────────────────────────────────────┐
  │ PASO    │ LO QUE DICE EL MENSAJE                       │
  ├─────────┼──────────────────────────────────────────────┤
  │ 1       │ "Empecé a trabajar"                          │
  │ 2       │ "Encontré N leads en el Google Sheets"       │
  │ 3       │ "Estoy procesando el lead 1 de N"            │
  │ 4       │ "Lead 1 listo — formulario llenado ✓"        │
  │ 5       │ "Estoy procesando el lead 2 de N"            │
  │ 6       │ "Lead 2 listo — captura subida a Drive ✓"    │
  │ ...     │ ...                                          │
  │ N       │ "Terminé. Resumen: 4 exitos, 1 error"        │
  │ FINAL   │ [Se cierra la conexión]                      │
  └─────────┴──────────────────────────────────────────────┘

Mientras tanto, en el navegador:

  ┌──────────────────────────────────────────┐
  │  ● Empecé a trabajar                     │
  │  ● Encontré N leads                     │
  │  ● Procesando lead 1/N... ████████░░░░  │
  │  ● Lead 1 listo ✓                       │
  │  ● Procesando lead 2/N... ██████░░░░░░  │
  │  ● Terminado (4 exitos, 1 error)        │
  └──────────────────────────────────────────┘
```

## ¿Qué pasaría si no existiera EventQueue?

- El usuario haría clic en "Iniciar" y la pantalla se quedaría **congelada** sin mostrar nada
- Después de varios minutos aparecería el resultado final
- El usuario no sabría si el programa se colgó o sigue trabajando
- No podría cancelar a tiempo si ve que algo sale mal


