# Sistema de Automatización de Pruebas de Formularios — UTEL Lead Tester


**Contenido del documento:** requisitos, diseño, documentación técnica y guía de usuario.

---

# Índice

1. **Introducción**
   - 1.1 ¿Qué es el proyecto?
   - 1.2 Problema que resuelve
   - 1.3 Alcance

2. **Sección 1 — Documentación de Requisitos**
   - 1.1 Objetivo del proyecto
   - 1.2 Actores y casos de uso
   - 1.3 Historias de usuario
   - 1.4 Funcionalidades del sistema
   - 1.5 Requisitos no funcionales

3. **Sección 2 — Documentación de Diseño**
   - 2.1 Arquitectura general
   - 2.2 Flujo de un lead, paso a paso
   - 2.3 Estructura interna del sistema
   - 2.4 Datos que maneja el sistema
   - 2.5 Patrones de diseño implementados
   - 2.6 Principios SOLID aplicados
   - 2.7 Buenas prácticas

4. **Sección 3 — Documentación Técnica**
   - 3.1 Requisitos del equipo
   - 3.2 Instalación paso a paso
   - 3.3 Configuración del sistema
   - 3.4 Interfaz de programación (API)
   - 3.5 Estructura de carpetas

5. **Sección 4 — Documentación de Usuario**
   - 4.1 Puesta en marcha
   - 4.2 Cómo usar la interfaz web
   - 4.3 Preguntas frecuentes (FAQ)

6. **Glosario**

---

# Introducción

## 1.1 ¿Qué es el proyecto?

**UTEL Lead Tester** es un sistema que automatiza la prueba de los formularios de captación de
leads (clientes potenciales) de los sitios web de CMS. En lugar de que una
persona abra el navegador, navegue al sitio, llene el formulario a mano, envíe los datos y
verifique el resultado para cada lead, el sistema lo hace solo, por lotes y de forma masiva.

Un **lead** es un cliente potencial: una persona interesada en estudiar que deja sus datos
(nombre, correo, teléfono, programa de interés) en un formulario de una página web.

El sistema recibe una lista de leads desde una hoja de cálculo de Google, y por cada uno:

1. Abre el sitio web del programa educativo en **Google Chrome**.
2. Llena el formulario con datos de prueba (nombre y teléfono ficticios, correo único por lead).
3. Envía el formulario.
4. Verifica en el sistema de gestión **Inconcert** que el lead quedó registrado.
5. Toma una **captura de pantalla** como evidencia a los campos Origen ID y Programa de Interes para guardar en Google Drive.
6. Anota el resultado (éxito o error) en la hoja de cálculo en la fila y columna correspondiente.

## 1.2 Problema que resuelve

Antes de este sistema, probar los formularios era un proceso manual y lento:
una persona debía repetir la misma secuencia de pasos decenas de veces al día,
navegando sitio por sitio y anotando resultados a mano. Además, los formularios cambian
constantemente (nuevos campos, nuevas políticas de privacidad, bloqueos anti-robot).

El sistema resuelve esto al:

- **Automatizar** el ciclo completo de prueba, de principio a fin.
- **Procesar lotes**: toma la lista completa de leads de la semana actual de una hoja de cálculo y los recorre
  sin intervención.
- **Dar evidencia**: cada lead procesado con éxito queda respaldado con una captura de
  pantalla guardada en Google Drive y el enlace se anota en la hoja.
- **Reportar errores**: si algo falla, el motivo se anota en la hoja de cálculo junto al lead y en la Interfaz de Usuario.
- **Funcionar en tiempo real**: el operador observa el avance (éxitos y errores) mientras
  el proceso corre.

## 1.3 Alcance

- **Soporta 14 países** (México, Perú, Colombia, Ecuador, Argentina, Bolivia, Chile, Estados
  Unidos, República Dominicana, Paraguay, Guatemala, El Salvador, Panamá y Global) y dos
  **flujos de trabajo** por país (sitios CMS y sitios de universidad).
- Se integra con **Google Sheets** (leer leads y escribir resultados), **Google Drive**
  (guardar capturas) y **Inconcert** (verificar el registro del lead).
- Se controla desde una **interfaz web local** que se abre en el navegador.

---

# Sección 1 — Documentación de Requisitos

## 1.1 Objetivo del proyecto

El objetivo es reducir a cero la intervención manual en la prueba de formularios de
captación: el operador solo elige el país, el flujo y la hoja de cálculo, y el sistema
procesa todos los leads de la lista, dejando en la misma hoja el resultado de cada uno
(con enlace a la captura de pantalla como evidencia).

## 1.2 Actores y casos de uso

**Actores del sistema:**

| Actor | Descripción |
|---|---|
| **Operador** | Persona que inicia, supervisa y detiene el proceso desde la interfaz web |
| **Sistema emisor** | Un sistema externo que podría enviar leads al servidor mediante la API (los leads hoy se leen de la hoja de cálculo) |
| **Google Sheets / Drive** | Sistema externo: provee la lista de leads, recibe resultados y guarda las capturas |
| **Inconcert** | Sistema externo de gestión: recibe el registro del lead y permite verificar que se creó |

**Casos de uso principales:**

| Caso | Nombre | Descripción |
|---|---|---|
| CU-01 | Iniciar el proceso | El operador elige país, flujo y hoja de cálculo y pulsa «Iniciar». El sistema lee los leads de la hoja |
| CU-02 | Procesar un lead | El sistema llena el formulario con datos de prueba, lo envía y valida el resultado |
| CU-03 | Verificar el registro | El sistema ingresa a Inconcert, busca el correo del lead y confirma su registró |
| CU-04 | Guardar evidencia | El sistema toma una captura de pantalla del registro y la sube a Google Drive |
| CU-05 | Registrar el resultado | El sistema escribe en la hoja de cálculo «éxito» (con enlace a la captura) o «error» (con el motivo) |
| CU-06 | Supervisar en vivo | El operador ve en la interfaz web el avance de cada lead en tiempo real |
| CU-07 | Detener el proceso | El operador puede cancelar el proceso en cualquier momento desde la interfaz |

## 1.3 Historias de usuario

1. **Como operador**, quiero elegir el país y el flujo antes de iniciar, para probar
   exactamente los formularios que me interesan.
2. **Como operador**, quiero ver el progreso en tiempo real (qué lead se está procesando y
   su resultado), para saber si el proceso va bien sin abrir la hoja de cálculo.
3. **Como administrador**, quiero que cada lead procesado quede con su resultado y su
   captura de pantalla en la hoja de cálculo, para tener evidencia verificable.
4. **Como administrador**, quiero detener el proceso en cualquier momento, para no gastar
   recursos si detecto un problema.
5. **Como mantenedor**, quiero que agregar un país nuevo no implique reescribir la lógica
   del sistema, sino solo agregar su configuración.

## 1.4 Funcionalidades del sistema

| Funcionalidad | Descripción |
|---|---|
| Lectura de leads | Lee la lista de leads (país, nivel, URL del sitio, tipo de formulario) desde una hoja de cálculo de Google |
| Filtrado por flujo | Filtra los leads según el flujo elegido (sitios CMS o sitios de Universidad) sin modificar el código |
| Datos de prueba | Genera un nombre y un teléfono ficticios (formato según el país) y un correo único por lead |
| Llenado del formulario | Detecta el formulario en la página (lateral, footer o tarjeta) y llena todos sus campos: modalidad, área, programa, nombre, correo, teléfono, canal de preferencia |
| Consentimiento de privacidad | Marca automáticamente todos los checkboxes de privacidad y consentimiento (por ejemplo, el consentimiento para contacto multicanal exigido por la Ley 2300 de 2023 en Colombia) |
| Envío y validación | Envía el formulario y lee el estado final de los campos para confirmar que se llenó correctamente |
| Verificación en Inconcert | Ingresa al sistema de gestión, busca el lead por su correo y confirma el registro |
| Captura de evidencia | Toma una captura de pantalla del registro y la sube a Google Drive |
| Registro de resultados | Escribe en la hoja de cálculo el resultado de cada lead: éxito con enlace a la captura, o error con el motivo |
| Supervisión en tiempo real | Emite eventos en vivo hacia la interfaz web (lead en proceso, éxito, error, resumen final) |
| Cancelación segura | Permite detener el proceso en curso sin dejar la hoja a medio escribir |
| Robustez ante bloqueos | Evita bloqueos anti-robot con configuración de Chrome (modo sigiloso, esperas aleatorias, perfil persistente) y reintenta cuando un sitio bloquea el acceso |

## 1.5 Requisitos no funcionales

| Categoría | Requisito |
|---|---|
| Rendimiento | Procesa varios leads en paralelo con un límite configurable (1 por defecto), para aprovechar el equipo sin saturarlo |
| Robustez | Cada etapa tiene un tiempo máximo de espera; si se supera, el lead se marca con el error y el proceso continúa con el siguiente |
| Disponibilidad | Si un sitio falla (bloqueo, cambio de diseño), el resto de los leads se sigue procesando |
| Seguridad | Las credenciales (usuario y contraseña de Inconcert, ID de la hoja, modos de autenticación de Google) se guardan en un archivo de configuración local (`.env`) y las credenciales de Google en archivos JSON separados |
| Compatibilidad | Requiere Google Chrome instalado en el equipo donde corre el sistema |
| Observabilidad | Cada paso del proceso queda registrado en un log con fecha y hora, para diagnosticar cualquier fallo |
| Usabilidad | La interfaz web es una sola página con los controles básicos: país, flujo, hoja, iniciar, detener y estado en vivo |
| Portabilidad | Se entrega con un entorno virtual de Python incluido: se instala una sola vez y se ejecuta con un comando |

---

# Sección 2 — Documentación de Diseño

## 2.1 Arquitectura general

El sistema es una aplicación **web local** organizada en tres niveles: una interfaz web
(por donde opera la persona), un servidor local (que coordina todo) y los sistemas
externos con los que se comunica (Google Sheets, Google Drive, los sitios de los programas
educativos e Inconcert).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    1. INTERFAZ WEB  (navegador del operador)                 │
│                                                                             │
│   El operador elige país, flujo y hoja de cálculo, inicia el proceso        │
│   y observa en tiempo real el avance de cada lead (exitos y errores)        │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     2. SERVIDOR LOCAL  (coordinación)                       │
│                                                                             │
│   · Lee la lista de leads desde la hoja de cálculo de Google                │
│   · Por cada lead: llena el formulario del sitio del programa educativo     │
│     con datos de prueba (nombre, teléfono y correo únicos)                  │
│   · Verifica en Inconcert que el lead quedó registrado y toma una           │
│     captura de pantalla que guarda en Google Drive                          │
│   · Anota el resultado (exito o error, con enlace a la captura) en la       │
│     hoja de cálculo                                                         │
└─────────────┬───────────────────────────────┬───────────────────────────────┘
              │                               │
              ▼                               ▼
┌────────────────────────────┐   ┌────────────────────────────────────────────┐
│  3. GOOGLE SHEETS          │   │  4. SITIO DEL PROGRAMA EDUCATIVO           │
│  (la hoja de cálculo:      │   │  (la landing page con el formulario)       │
│   leads de entrada,        │   │                                            │
│   resultados y capturas)   │   │  5. INCONCERT (verificación del registro)  │
│                            │   │   + GOOGLE DRIVE (almacén de capturas)     │
└────────────────────────────┘   └────────────────────────────────────────────┘
```

La comunicación con Google Sheets, Google Drive e Inconcert se realiza mediante las APIs
oficiales de cada servicio, autenticadas con las credenciales de Google e Inconcert.

## 2.2 Flujo de un lead, paso a paso

Cuando el operador inicia el proceso, el sistema recorre los siguientes pasos:

```
1. Leer la lista de leads desde la hoja de cálculo.
       │
       ▼
2. Para cada lead, preparar los datos de prueba:
   nombre y teléfono ficticios + correo único ejemplo: (test030826N001@testingUtel.com)
       │
       ▼
3. Abrir el sitio del programa educativo en Google Chrome
   (con perfil persistente y configuración anti-detección).
       │
       ▼
4. Localizar el formulario en la página:
   · Formulario lateral      → se abre desde un botón de la página
   · Formulario de pie       → se baja hasta el final de la página
   · Formulario tarjeta      → si no existe, se busca la página del producto
       │
       ▼
5. Llenar el formulario:
   · Modalidad y área de estudio
   · Programa (se selecciona del listado del sitio)
   · Nombre, correo y teléfono de prueba
   · Canal de preferencia
   · Checkboxes de privacidad y consentimiento (todos)
       │
       ▼
6. Enviar el formulario y validar: se relee el estado de los campos
   para confirmar que se llenaron y se marcaron los consentimientos.
       │
       ▼
7. Verificar en Inconcert: ingresar, buscar el correo del lead
   y confirmar que el registro existe.
       │
       ▼
8. Tomar una captura de pantalla del registro y subirla a Google Drive.
       │
       ▼
9. Escribir el resultado en la hoja de cálculo:
   · Exito      → enlace a la captura de pantalla
   · Error      → motivo legible del fallo
   y avisar a la interfaz web en tiempo real.
```

Si cualquiera de los pasos 3 a 8 falla, el sistema anota el error junto al lead y continúa
con el siguiente, de modo que un fallo puntual no detiene el lote completo.

## 2.3 Estructura interna del sistema

El sistema se divide en módulos, cada uno con una responsabilidad clara:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                      ESTRUCTURA INTERNA DEL SISTEMA                         │
│                                                                            │
│   ┌───────────┐   ┌──────────────┐   ┌─────────────────────────────────┐   │
│   │   web/    │──►│   pipeline/  │──►│           automation/           │   │
│   │ recepción │   │ coordinador  │   │                                 │   │
│   │ (página   │   │ general de   │   │  ┌───────────┐  ┌─────────────┐ │   │
│   │  web y    │   │ los lotes de │   │  │ browser   │  │  form/      │ │   │
│   │  API)     │   │ leads        │   │  │ (Chrome   │  │ (llenado    │ │   │
│   └───────────┘   └──────┬───────┘   │  │  sigiloso) │  │  del form)  │ │   │
│                          │           │  └───────────┘  └──────┬──────┘ │   │
│   ┌───────────┐   ┌──────▼───────┐   │  ┌──────────────────────▼──────┐ │   │
│   │  events/  │◄──│    sheets/   │   │  │  inconcert/                 │ │   │
│   │ altavoz   │   │ (lectura y  │   │  │  (verificación del registro │ │   │
│   │ (avisos   │   │  escritura  │   │  │   + captura de pantalla)    │ │   │
│   │  en vivo) │   │  de la hoja)│   │  └─────────────────────────────┘ │   │
│   └───────────┘   └─────────────┘   └─────────────────────────────────┘   │
│                                                                            │
│   ┌────────────┐   ┌────────────────────────────────────────────────────┐ │
│   │    core/   │   │      config/   (ajustes, países y credenciales)   │ │
│   │  cimientos │   │      · settings    · países    · credenciales     │ │
│   │  del       │   │        de Google · config de cada país/formulario│ │
│   │  sistema   │   │      · datos de prueba (nombres y teléfonos)      │ │
│   └────────────┘   └────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

| Módulo | Analogía | Responsabilidad |
|---|---|---|
| `web/` | La recepción | Expone la página web que usa el operador y la API: iniciar, detener, estado, avisos en vivo |
| `pipeline/` | El coordinador general | Organiza el lote: lee los leads, reparte el trabajo, junta resultados y escribe en la hoja |
| `automation/` | El equipo de llenado | Abre Chrome, llena los formularios, verifica en Inconcert y toma capturas |
| `automation/form/` | El rellenador de formularios | Detecta el formulario, elige la estrategia por país, llena campos, marca consentimientos y valida |
| `automation/inconcert/` | El verificador | Ingresa a Inconcert, busca el lead, prepara la vista y toma la captura |
| `sheets/` | El cuaderno de registros | Lee los leads de la hoja y escribe los resultados (éxito o error con motivo) |
| `events/` | El altavoz | Anuncia en tiempo real cada avance hacia la interfaz web |
| `core/` | Los cimientos | Modelos de datos, excepciones, datos de prueba y utilidades; no depende de ningún otro módulo |
| `config/` | La caja de ajustes | Variables de entorno, catálogo de países, configuración de cada formulario y credenciales de Google |

## 2.4 Datos que maneja el sistema

| Dato | Origen | Uso |
|---|---|---|
| **Lead** (fila de la hoja) | Hoja de cálculo de Google | Número de fila, país, nivel académico, URL del sitio, tipo de formulario, cliente |
| **Solicitud de proceso** | Interfaz web | País, flujo (CMS / universidad), ID de la hoja de cálculo y pestaña |
| **Datos de prueba** | Generados por el sistema | Nombre ficticio (de una lista), teléfono ficticio (formato por país), correo único por lead con formato `test{ddmmaa}N{nnn}@testingUtel.com` |
| **Contexto de llenado** | Coordinador → rellenador | Contenedor del formulario, nivel, correo, nombre y teléfono de prueba |
| **Resultado** | Sistema → hoja de cálculo | Éxito (con enlace a la captura) o error (con motivo legible) |

Los datos de prueba (nombres y plantillas de teléfono por país) están en archivos de
configuración, separados del código, para poder ajustarlos sin tocar la lógica.

## 2.5 Patrones de diseño implementados

| Patrón | Dónde se aplica | Para qué sirve |
|---|---|---|
| **Estrategia (Strategy)** | Módulo `fillers/`: `CmsFiller` y `FallbackFiller`, ambos bajo el contrato `IFormFiller` | Llenar el formulario con una táctica distinta según el país y el tipo de sitio, sin que el resto del sistema conozca los detalles |
| **Registro (Registry)** | `engine/registry.py` | Elegir la estrategia correcta según el país y la URL; siempre devuelve una estrategia válida, nunca un vacío |
| **Fachada (Facade)** | `core/fake_data/service.py` (`FakeDataService`) | Un único punto de entrada para generar los datos de prueba, ocultando la complejidad de los proveedores de nombres y teléfonos |
| **Objeto de transferencia (DTO)** | `FillContext`, `LeadRow`, `RunRequest` | Empaquetar los datos que viajan entre componentes, evitando funciones con listas interminables de parámetros |
| **Inyección de dependencias** | `pipeline/orchestrator.py` | El coordinador recibe por constructor lo que necesita (lector, escritor, capturas, altavoz); no lo fabrica él mismo |
| **Observador (Observer)** | `events/queue.py` → interfaz web | Avisar en tiempo real al navegador del operador (lead en proceso, éxito, error, resumen final) |
| **Singleton** | Servicios únicos creados al arrancar (lector de hoja, escritor, gestor de capturas) | Una sola instancia compartida de cada servicio para todo el proceso |
| **Método plantilla (Template Method)** | `FormFillerOrchestrator.fill()` | Fija el esqueleto del ciclo (navegar, preparar, detectar, llenar, validar) mientras las estrategias concretas definen los detalles |

## 2.6 Principios SOLID aplicados

| Principio | Cómo se cumple en el sistema |
|---|---|
| **S — Responsabilidad única** | Cada clase hace una sola cosa: `SelectHandler` (listas desplegables), `ContactFields` (datos de contacto), `PrivacyHandler` (checkboxes de privacidad), `FormSubmitter` (envío), `Detectors` (detección del formulario), `Registry` (selección de estrategia) |
| **O — Abierto / Cerrado** | Agregar un país nuevo no modifica el orquestador: solo se agrega su configuración al catálogo de países y formularios. El sistema está abierto a extensión, cerrado a modificación |
| **L — Sustitución de Liskov** | Cualquier estrategia que cumpla el contrato `IFormFiller` puede reemplazar a otra sin romper el comportamiento del sistema |
| **I — Segregación de interfaces** | Los contratos son mínimos: `IFormFiller` tiene solo dos operaciones (`prepare` y `fill`); `IEventPublisher` solo las operaciones de aviso. Nadie depende de métodos que no usa |
| **D — Inversión de dependencias** | El coordinador depende de contratos (protocolos) e inyección, nunca de clases concretas; los módulos de alto nivel no dependen de los de bajo nivel |

## 2.7 Buenas prácticas

1. **Configuración guiada por datos (data-driven):** los 14 países, sus formularios y sus
   flujos viven en configuración, no en condiciones dentro del código. No existe un
   `if país == ...` por país en la lógica principal.
2. **Funciones puras separadas:** la normalización de textos, niveles y modalidades vive en
   funciones sin dependencia del navegador, fáciles de probar de forma aislada.
3. **Concurrencia controlada:** los leads se procesan en paralelo con un límite máximo
   configurable (semáforo) y un contador atómico para que los correos de prueba nunca se
   repitan.
4. **Tiempos límite por etapa y reintentos:** cada etapa tiene un tiempo máximo; ante
   bloqueos del sitio (Cloudflare) se reintenta con estrategias alternativas.
5. **Simulación de comportamiento humano:** Chrome se abre con un perfil persistente, modo
   sigiloso, esperas aleatorias entre acciones y una identidad de navegador real, para
   evitar que los sitios bloqueen al sistema como robot.
6. **Validación posterior al envío:** el sistema relee el estado del formulario después de
   llenarlo (incluidos los checkboxes de consentimiento) antes de declarar el éxito; así se
   evitan falsos positivos.
7. **Registro (log) de cada paso:** cada acción queda registrada con fecha y hora, lo que
   permite diagnosticar cualquier fallo del lote.
8. **Manejo de errores explícito:** cada operación devuelve el motivo del fallo en texto
   legible, y ese motivo se anota en la hoja de cálculo junto al lead y en la interfaz de Usuario.
9. **Reglas de estilo internas:** métodos cortos (menos de 30 líneas), retorno temprano
   para evitar anidaciones y comentarios con formato uniforme.
10. **Seguridad de credenciales:** las claves de acceso (Inconcert, Google) se cargan desde
    el archivo de entorno `.env` y archivos JSON de credenciales, fuera del código fuente.

---

# Sección 3 — Documentación Técnica

## 3.1 Requisitos del equipo

| Requisito | Detalle |
|---|---|
| Sistema operativo | Windows 10 u 11 (64 bits) |
| Python | 3.11 o superior |
| Navegador | **Google Chrome** instalado (el sistema lo controla directamente) |
| Cuentas | Cuenta de Google con acceso a la hoja de cálculo, Google Drive e Inconcert |
| Espacio | ~2 GB para el entorno virtual y datos del navegador |

## 3.2 Instalación paso a paso

```
1. Abrir una terminal (Símbolo del sistema o PowerShell) en la carpeta del proyecto
   (la que contiene la carpeta "app").

2. Crear el entorno virtual de Python (solo la primera vez):

      python -m venv app\venv

3. Activar el entorno virtual:

      app\venv\Scripts\activate

4. Instalar las dependencias:

      pip install -r app\requirements.txt

5. Copiar el archivo de configuración de ejemplo:

      copy app\.env.example app\.env

6. Editar app\.env y completar:
   · INCONCERT_USER e INCONCERT_PASSWORD  → credenciales de Inconcert
   · GOOGLE_SHEET_ID                      → ID de la hoja de cálculo
   · GOOGLE_AUTH_MODE                     → "service_account" u "oauth"
     (ver sección 3.3)

7. Colocar las credenciales de Google en app\config\data\:
   · google_credentials.json              → cuenta de servicio (modo service_account)
   · google_oauth_client_secret.json      → cliente OAuth (modo oauth)
   · google_oauth_token.json              → token generado al autorizar (modo oauth)

8. Verificar que Google Chrome esté instalado en el equipo.

9. Iniciar el sistema:

      python -m uvicorn main:app --host 127.0.0.1 --port 8000

10. Abrir en el navegador:  http://127.0.0.1:8000
```

Si se desea cambiar el puerto, se modifica la variable `PORT` en `.env` o el parámetro
`--port` del comando.

## 3.3 Configuración del sistema

**Archivo `.env`** (variables de Entorno):

| Variable | Descripción |
|---|---|
| `INCONCERT_USER` / `INCONCERT_PASSWORD` | Usuario y contraseña del sistema Inconcert |
| `GOOGLE_SHEET_ID` | Identificador de la hoja de cálculo de Google |
| `GOOGLE_AUTH_MODE` | Modo de autenticación de Google: `service_account` (cuenta de servicio compartida) u `oauth` (cada usuario autoriza su cuenta) |
| `GOOGLE_CREDENTIALS_PATH` | Ruta del JSON de la cuenta de servicio |
| `GOOGLE_OAUTH_CLIENT_SECRET_PATH` | Ruta del JSON del cliente OAuth |
| `GOOGLE_OAUTH_TOKEN_PATH` | Ruta del JSON del token OAuth generado |
| `LEAD_TIMEOUT_SECONDS` | Tiempo máximo (segundos) para procesar cada lead |
| `MAX_WORKERS` | Máximo de leads procesados en paralelo |
| `PORT` | Puerto del servidor web (por defecto 8000) |

**Catálogo de países y formularios** (`config/`):

- `countries.py` — los 14 países soportados y los prefijos de URL por flujo.
- `form_configs.py` — la configuración de cada formulario por país: selectores de campos,
  botones de envío, equivalencias de niveles académicos y textos de los llamados a la
  acción.

**Datos de prueba** (`config/data/`):

- `names.json` — lista de nombres ficticios.
- `phones.json` — plantillas de teléfono por país.

**Credenciales de Google** (`config/data/google_oauth_token.json`): los archivos JSON de cuenta de servicio,
cliente OAuth y token. En modo OAuth, si no existe un token válido, el sistema abre el
navegador para autorizar la cuenta y guarda el token automáticamente. 

## 3.4 Interfaz de programación (API)

El servidor expone los siguientes puntos de acceso (todos en `http://127.0.0.1:8000`):

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Página web de la interfaz de usuario |
| POST | `/api/run` | Inicia el proceso. Parámetros: `country` (país), `flow` (cms o universidad), `sheet_id` (ID de la hoja), `sheet_tab` (pestaña) |
| GET | `/api/stream` | Conexión de eventos en tiempo real (SSE) con el avance del proceso |
| POST | `/api/stop` | Detiene el proceso en curso |
| GET | `/api/status` | Indica si hay un proceso en curso |
| GET | `/api/countries` | Devuelve la lista de países disponibles |

Ejemplo de inicio desde la terminal:

```
curl -X POST http://127.0.0.1:8000/api/run ^
  -d "country=Colombia" ^
  -d "flow=cms" ^
  -d "sheet_id=1gdI5ViJoLxIF5tbMuCmNCB5clLlaIvue" ^
  -d "sheet_tab=Leads"
```

## 3.5 Estructura de carpetas

```
app/
├── main.py                  → punto de entrada del servidor
├── requirements.txt         → dependencias de Python
├── .env                     → configuración local (usuario, credenciales)
├── .env.example             → plantilla de configuración
├── chrome_profile/          → perfil persistente de Chrome (se crea solo)
├── static/                  → estilos e imágenes de la interfaz web
├── templates/               → plantilla de la página web
├── web/                     → interfaz web y API (rutas, eventos SSE)
├── pipeline/                → coordinador general de los lotes de leads
├── automation/
│   ├── browser.py           → control de Chrome (perfil persistente, sigiloso)
│   ├── common/              → utilidades anti-detección (Cloudflare, scroll)
│   ├── form/
│   │   ├── contracts/       → contratos y objetos de transferencia
│   │   ├── engine/          → orquestador, detección, registro de estrategias
│   │   ├── fillers/         → estrategias de llenado por país
│   │   └── handlers/        → acciones concretas: selects, campos, checkboxes, envío
│   └── inconcert/           → autenticación, búsqueda y captura en Inconcert
├── sheets/                  → lectura y escritura de Google Sheets
├── events/                  → cola de eventos en tiempo real (SSE)
├── core/                    → modelos, excepciones, datos de prueba, utilidades
├── config/                  → ajustes, países, formularios, credenciales
└── docs/                    → documentación del proyecto
```

---

# Sección 4 — Documentación de Usuario

## 4.1 Puesta en marcha

1. Abrir una terminal y activar el entorno virtual:

   ```
   app\venv\Scripts\activate
   ```

2. Iniciar el sistema:

   ```
   python -m uvicorn main:app --host 127.0.0.1 --port 8000
   ```

3. Abrir en el navegador: `http://127.0.0.1:8000`

Cuando el sistema arranca por primera vez, abre una ventana de **Google Chrome** con su
perfil de trabajo; esa ventana es la que el sistema usa para llenar los formularios. No se
debe cerrar durante el proceso.

## 4.2 Cómo usar la interfaz web

| Control | Cómo usarlo |
|---|---|
| **País** | Seleccionar el país de los formularios a probar (por ejemplo, Colombia) |
| **Flujo** | Seleccionar el flujo: sitios CMS o sitios de universidad (según el país) |
| **ID de la hoja de cálculo** | Pegar el identificador de la hoja de Google que contiene los leads |
| **Hoja (pestaña)** | Seleccionar la pestaña concreta dentro de la hoja |
| **Iniciar** | Comienza el procesamiento del lote de leads |
| **Detener** | Cancela el proceso en curso |
| **Estado** | Muestra si hay un proceso activo |
| **Progreso en vivo** | Lista de eventos: cada lead en proceso, su resultado (éxito con captura o error con motivo) y el resumen final al terminar |

**Sugerencias de uso:**

- La hoja de cálculo debe ser una **hoja nativa de Google** (ver FAQ, punto 4.3.1).
- Cada lead debe tener, al menos, país, nivel académico, URL del sitio y tipo de
  formulario.
- El resultado queda anotado en la misma hoja, junto a cada lead, con el enlace a la
  captura de pantalla en caso de éxito.

## 4.3 Preguntas frecuentes (FAQ)

**4.3.1 El sistema marca el error «This operation is not supported for this document» al
leer la hoja de cálculo.**

La hoja es un archivo de Excel (`.xlsx`) subido a Google Drive, no una hoja nativa de
Google. Solución: abrir el archivo en Google Sheets y usar **Archivo → Guardar como →
Hoja de cálculo de Google**. El sistema solo puede trabajar con hojas nativas.

**4.3.2 El sistema no abre Chrome o el proceso falla al navegar.**

Verificar que **Google Chrome** esté instalado y actualizado en el equipo. Si el perfil
persistente se corrompió, se puede borrar la carpeta `chrome_profile` y el sistema lo
recrea al iniciar.

**4.3.3 No se pueden leer ni escribir en Google Sheets.**

Revisar en el `.env`: el ID de la hoja (`GOOGLE_SHEET_ID`), el modo de autenticación
(`GOOGLE_AUTH_MODE`) y que la cuenta de Google tenga acceso a la hoja. En modo OAuth, si
el token caducó, borrar `google_oauth_token.json` y volver a iniciar: el sistema abrirá el
navegador para autorizar de nuevo.

**4.3.4 El puerto ya está en uso al iniciar el sistema.**

Cambiar el puerto con `--port` en el comando de inicio (por ejemplo, `--port 8001`) o
modificar `PORT` en `.env`.

**4.3.5 El proceso termina muy rápido y no procesa leads.**

La hoja no tiene leads que coincidan con el país y el flujo elegidos. Revisar que la
pestaña seleccionada contenga filas con el país y los prefijos de URL del flujo indicado.

**4.3.6 ¿Cómo se detiene un proceso que se quedó colgado?**

Usar el botón **Detener** de la interfaz. El sistema cancela el proceso y escribe el estado
«cancelado» en los leads que estaban en curso.

---

# Glosario

| Término | Significado |
|---|---|
| **Lead** | Cliente potencial: persona interesada que deja sus datos en un formulario web |
| **Landing page** | Página de aterrizaje del programa educativo, donde vive el formulario |
| **Flujo** | Familia de sitios con el mismo tipo de implementación: CMS o universidad |
| **API** | Interfaz de programación: conjunto de puntos de acceso que permite a los sistemas comunicarse |
| **SSE** | Server-Sent Events: mecanismo por el cual el servidor envía avisos en vivo al navegador |
| **DTO** | Objeto de transferencia de datos: paquete estructurado que viaja entre componentes |
| **OAuth** | Protocolo de autorización que permite a una aplicación acceder a una cuenta de Google sin conocer su contraseña |
| **Cuenta de servicio** | Identidad de Google creada para que el sistema acceda a Sheets y Drive sin intervención del usuario |
| **Playwright** | Biblioteca que permite controlar el navegador (Google Chrome) mediante código |
| **Cloudflare** | Servicio de protección de sitios web que puede bloquear automatizaciones; el sistema aplica técnicas para evitarlo |
| **Webhook** | Llamada automática de un sistema a otro cuando ocurre un evento |
| **Entorno virtual** | Carpeta aislada con la versión exacta de Python y de las bibliotecas que el proyecto necesita |
