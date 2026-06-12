// Shared utility functions — included at top of every domain script by ScriptLoader
// To use: ScriptLoader.evaluate(page, "form_detection.js") which internally
// includes common.js at the top of the JS string.

const CODEX_COMMON = {
    norm: (v) => String(v || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim(),

    clean: (v) => String(v || '').trim(),

    visible: (el) => {
        if (!el || el.disabled) return false;
        const style = window.getComputedStyle(el);
        const box = el.getBoundingClientRect();
        return style.display !== 'none'
            && style.visibility !== 'hidden'
            && box.width > 0
            && box.height > 0;
    },

    fieldVisible: (el) => {
        if (CODEX_COMMON.visible(el) && el.type !== 'hidden') return true;
        return false;
    },

    badValues: new Set(['', '-', '--', 'seleccionar', 'selecciona', 'select', 'choose']),

    isBad: (v) => CODEX_COMMON.badValues.has(CODEX_COMMON.norm(v)),

    blockedTerms: [
        'whatsapp', 'politica', 'privacidad', 'aviso', 'terminos',
        'solicitar informacion', 'calcula tu beca', 'enviar',
        'sugerencias', 'modalidad', 'oferta academica', 'aspirantes',
        'conoce utel', 'comunidad', 'becas', 'campus virtual',
        'obtener beca', 'inscripciones', 'estudiantes',
    ],

    isBlocked: (text, href) => {
        const t = CODEX_COMMON.norm(text);
        const h = CODEX_COMMON.norm(href || '');
        return CODEX_COMMON.blockedTerms.some((term) => t.includes(term) || h.includes(term));
    },

    keyFor: (el) =>
        `${el.name || ''} ${el.id || ''} ${el.placeholder || ''} ${el.type || ''} ${el.getAttribute('aria-label') || ''}`.toLowerCase(),

    labelText: (el, root) => {
        const id = el.id ? (root || document).querySelector(`label[for="${CSS.escape(el.id)}"]`)?.textContent || '' : '';
        const parentLabel = el.closest('label')?.textContent || '';
        return `${id} ${parentLabel}`;
    },

    hasSubmit: (root) => Array.from(root.querySelectorAll('button, input[type=submit], [role=button]'))
        .filter((el) => CODEX_COMMON.visible(el))
        .some((el) => /enviar|solicitar|informaci|beca|comienza|registr/i.test(el.textContent || el.value || '')),
};
