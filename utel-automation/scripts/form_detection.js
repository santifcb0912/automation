// Form detection and scoring
// Usage: ScriptLoader.evaluate(page, "form_detection.js", { root: document, formType: "tarjeta", tarjetaProductOpened: false })

(root, params = {}) => {
    const { formType, tarjetaProductOpened } = params || {};
    const CC = CODEX_COMMON;

    // ---------------------------------------------------------------- //
    // 1. Find form scope by type
    // ---------------------------------------------------------------- //
    function findFormScope() {
        if (formType === 'tarjeta' && !tarjetaProductOpened) {
            return null; // Don't fill if no product page opened
        }

        if (formType === 'lateral') {
            const lateral = root.querySelector('#LateralBLC');
            if (lateral && CC.visible(lateral)) return lateral;
            const panel = findLateralPanel();
            if (panel) return panel;
            return null;
        }

        const formIds = ['FooterBLC', 'LateralBLC', 'TarjetaBLC'];
        for (const id of formIds) {
            const el = root.querySelector(`#${id}`);
            if (el && CC.visible(el)) return el;
        }

        const form = findBestForm();
        if (form) return form;

        return document.body;
    }

    // ---------------------------------------------------------------- //
    // 2. Score a form element to find best match
    // ---------------------------------------------------------------- //
    function scoreForm(rootEl) {
        let score = 0;
        for (const el of Array.from(rootEl.querySelectorAll('input, select, textarea'))) {
            if (!CC.fieldVisible(el)) continue;
            const key = CC.keyFor(el);
            if (key.includes('email') || key.includes('correo')) score += 4;
            if (key.includes('phone') || key.includes('tel')) score += 4;
            if (key.includes('name') || key.includes('nombre')) score += 3;
            if (key.includes('modality') || key.includes('area') || key.includes('program')) score += 2;
        }
        return score;
    }

    function findBestForm() {
        const forms = Array.from(root.querySelectorAll('form:visible'));
        let best = null;
        let bestScore = -1;
        for (const form of forms) {
            const s = scoreForm(form);
            if (s > bestScore) { best = form; bestScore = s; }
        }
        return best;
    }

    // ---------------------------------------------------------------- //
    // 3. Lateral panel detection
    // ---------------------------------------------------------------- //
    function scoreLateralPanel(el) {
        if (!CC.visible(el)) return 0;
        const box = el.getBoundingClientRect();
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
        if (box.left < viewportWidth * 0.50 && box.right < viewportWidth * 0.85) return 0;

        const text = CC.norm(el.textContent || '');
        let score = /tu meta est|completa el formulario|modalidad|area de interes|área de interés/.test(text) ? 5 : 0;
        const fields = Array.from(el.querySelectorAll('input, select, textarea')).filter(CC.fieldVisible);
        const keys = fields.map(CC.keyFor);
        if (keys.some((x) => x.includes('email') || x.includes('correo'))) score += 4;
        if (keys.some((x) => x.includes('phone') || x.includes('tel'))) score += 4;
        if (keys.some((x) => x.includes('name') || x.includes('nombre'))) score += 3;
        if (keys.some((x) => x.includes('modality') || x.includes('area') || x.includes('program'))) score += 2;
        return score;
    }

    function findLateralPanel() {
        const panels = Array.from(root.querySelectorAll('aside:visible, section:visible, form:visible, div:visible'));
        for (const panel of panels) {
            if (scoreLateralPanel(panel) >= 12) return panel;
        }
        return null;
    }

    // ---------------------------------------------------------------- //
    // 4. Contact form visible check
    // ---------------------------------------------------------------- //
    function contactFormExists() {
        const fields = Array.from(root.querySelectorAll('input, select, textarea'))
            .filter(CC.fieldVisible)
            .map(CC.keyFor);
        return fields.some((x) => x.includes('email') || x.includes('correo'))
            && fields.some((x) => x.includes('phone') || x.includes('tel'))
            && fields.some((x) => x.includes('name') || x.includes('nombre'));
    }

    // ---------------------------------------------------------------- //
    // 5. Form field state reader
    // ---------------------------------------------------------------- //
    function readFormState() {
        return {
            modality: root.querySelector("select[name='modality'], select#modality")?.value?.trim() || '',
            area: root.querySelector("select[name='area'], select#area")?.value?.trim() || '',
            program: root.querySelector("select[name='program'], select#program, input[name='program'], input#program")?.value?.trim() || '',
            first_name: getFieldValue("input#first_name, input[name='first_name'], input[name='name'], input[name*='nombre' i], input[id*='nombre' i]"),
            email: getFieldValue("input#email, input[name='email'], input[type='email'], input[name*='correo' i], input[id*='correo' i]"),
            phone: getFieldValue("input#phone, input[name='phone'], input[type='tel'], input[name*='telefono' i], input[id*='telefono' i], input[name*='celular' i], input[id*='celular' i], input[name*='mobile' i]"),
            has_checkbox: !!root.querySelector("input[type='checkbox']"),
            checkbox_checked: root.querySelector("input[type='checkbox']")?.checked ?? true,
        };
    }

    function getFieldValue(selector) {
        const el = root.querySelector(selector);
        return el?.value?.trim() || '';
    }

    // ---------------------------------------------------------------- //
    // 6. All fields debug listing
    // ---------------------------------------------------------------- //
    function listFields() {
        return Array.from(root.querySelectorAll('input, select, textarea')).map((el) => ({
            tag: el.tagName,
            type: el.type || '',
            name: el.name || '',
            id: el.id || '',
            placeholder: el.placeholder || '',
            value: el.type === 'password' ? '***' : (el.value || ''),
            options: el.tagName === 'SELECT'
                ? Array.from(el.options || []).map((o) => ({
                    text: (o.textContent || '').trim(),
                    value: o.value || '',
                })).slice(0, 10)
                : [],
        }));
    }

    // ---------------------------------------------------------------- //
    // 7. Footer fields ready check
    // ---------------------------------------------------------------- //
    function footerFieldsReady() {
        const fields = Array.from(root.querySelectorAll('input, select, textarea'))
            .filter(CC.fieldVisible)
            .map(CC.keyFor);
        return fields.some((x) => x.includes('email') || x.includes('correo'))
            && fields.some((x) => x.includes('phone') || x.includes('tel') || x.includes('telefono') || x.includes('celular') || x.includes('mobile'))
            && fields.some((x) => x.includes('name') || x.includes('nombre') || x.includes('first_name'));
    }

    return {
        findFormScope: findFormScope(),
        findLateralPanel: findLateralPanel(),
        contactFormExists: contactFormExists(),
        readFormState: readFormState(),
        listFields: listFields(),
        footerFieldsReady: footerFieldsReady(),
    };
}
