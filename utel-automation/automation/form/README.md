# automation/form/ — Reglas del flujo de formularios

## Reglas obligatorias

| # | Regla | Explicación |
|---|-------|-------------|
| 1 | **Solo selectores semánticos** | Cada campo se localiza por `name`, `id`, `data-*`, `aria-label`, `placeholder` o `label[for]`. Prohibido usar `human_click_point()`, coordenadas fijas, `page.evaluate()` con click por bounding box, o cualquier forma de posicionamiento por pixeles. |
| 2 | **Sin `force=True`** | Playwright `click(force=True)` y `fill(force=True)` están prohibidos. Si un elemento no es clickeable/visible, no se fuerza — se reporta el fallo. |
| 3 | **Sin `page.keyboard.type()`** | Usar solo `locator.fill()` para inputs de texto. `press()` solo para teclas de navegación (ArrowDown, Enter, Escape) cuando no haya alternativa semántica. |
| 4 | **Sin fallbacks ni refuerzos** | Cada paso tiene una única estrategia. Si falla, retorna `Optional[str]` con la razón. No hay plan B, reintentos con otra técnica, ni capas de caída. La única excepción documentada son los 4 intentos de programa en Universidad Mexico (Choices.js problemático), que será refactorizado cuando se tengan selectores estables. |
| 5 | **`Optional[str]` como firma** | Todo método que puede fallar retorna `Optional[str]`: `None` = éxito, `str` = razón del error. La razón debe ser descriptiva para que llegue a la columna del Sheet. |
| 6 | **Constructor Injection** | Los handlers reciben `page`, `form_scope`, `country` y dependencias por constructor. No crean instancias internamente ni importan providers. |
| 7 | **Columna E es la única fuente de verdad** | El `form_type` (Footer, Lateral, Tarjeta, Form LP) se lee del sheet. El sistema obedece ese valor. No infiere desde la URL, no sobreescribe. |
| 8 | **Orden de llenado CMS** | modalidad → área → programa → nombre → email → teléfono → checkbox de privacidad → enviar. Ningún paso se salta aunque falle el anterior. |
| 9 | **Sin emojis en logs** | Los mensajes de `logger.info/warning/error` son texto plano sin emojis. |
| 10 | **Comentarios en español** | Un comentario por método, línea descriptiva de qué hace. No se documenta el cómo. |
