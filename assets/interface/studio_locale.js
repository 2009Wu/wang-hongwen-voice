async () => {
    const module = await import(new URL("assets/" + LOCALE_ASSET, new URL("./", location.href)));
    const {names, rtl, copy} = STUDIO_LOCALES;
    const key = "studio-interface-language";
    const app = document.querySelector("gradio-app") || document;
    const menu = app.querySelector("#studio-locale-control") || await new Promise(resolve => {
        const observer = new MutationObserver(() => {
            const element = app.querySelector("#studio-locale-control");
            if (!element) return;
            observer.disconnect();
            clearTimeout(timeout);
            resolve(element);
        });
        observer.observe(app, {childList: true, subtree: true});
        const timeout = setTimeout(() => {
            observer.disconnect();
            resolve(null);
        }, 10000);
    });
    if (!menu || menu.dataset.ready) return;
    menu.dataset.ready = "true";
    const trigger = menu.querySelector(".studio-locale-toggle");
    const name = menu.querySelector(".studio-locale-name");
    const panel = menu.querySelector(".studio-locale-options");
    const list = panel.querySelector(".studio-locale-list");
    const search = panel.querySelector("input");
    const empty = panel.querySelector(".studio-locale-empty");
    const rows = [...list.querySelectorAll("li")];
    const options = [...list.querySelectorAll("button")];
    const aliases = {"en": "English", "zh-CN": "Mandarin Chinese Simplified 中文 普通话", "zh-TW": "Mandarin Chinese Traditional 中文 國語", "hi": "Hindi", "es": "Spanish", "ar": "Modern Standard Arabic", "fr": "French", "bn": "Bengali Bangla", "pt": "Portuguese", "id": "Indonesian", "ur": "Urdu", "ru": "Russian", "de": "German", "ja": "Japanese", "pcm": "Nigerian Pidgin", "arz": "Egyptian Arabic", "mr": "Marathi", "vi": "Vietnamese", "te": "Telugu", "sw": "Swahili", "ha": "Hausa"};
    const normalize = value => value.normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase().trim();
    const uploadCopies = [0, 1, 2].map(i => new Set(Object.values(copy).map(value => value.upload[i])));
    let locale = "zh-CN";
    let pinned = false;
    let frame = 0;

    function refreshLabels() {
        frame = 0;
        const labels = copy[locale];
        const visibleTabs = [...app.querySelectorAll('#studio-main-tabs [role="tab"]')];
        const tabIds = ["studio-create", "studio-history", "studio-help"];
        for (const button of visibleTabs) {
            const index = tabIds.indexOf(button.dataset.tabId);
            if (index === -1) continue;
            const text = [...button.childNodes].find(node => node.nodeType === Node.TEXT_NODE && node.data.trim());
            if (text && text.data.trim() !== labels.tabs[index]) text.data = labels.tabs[index];
        }
        for (const wrapper of app.querySelectorAll('.studio-file [data-testid="upload-text"]')) {
            const container = wrapper.closest('button[aria-dropeffect="copy"]');
            if (container && container.getAttribute("aria-label") !== labels.uploadName) {
                container.setAttribute("aria-label", labels.uploadName);
            }
            const label = wrapper.closest(".studio-upload-field")?.querySelector(".studio-field-label");
            if (container && label && container.getAttribute("aria-describedby") !== label.id) {
                container.setAttribute("aria-describedby", label.id);
            }
            const separator = wrapper.querySelector(".or");
            const texts = [...wrapper.childNodes, ...(separator?.childNodes || [])];
            for (const node of texts) {
                if (node.nodeType !== Node.TEXT_NODE) continue;
                const original = node.data.trim();
                const keyText = original.replace(/^-\s*|\s*-$/g, "");
                const index = uploadCopies.findIndex(values => values.has(keyText));
                if (index < 0) continue;
                const translated = index === 2 ? "- " + labels.upload[2] + " -" : labels.upload[index];
                if (original !== translated) node.data = node.data.replace(original, translated);
            }
        }
        const title = app.querySelector("#studio-hero-copy h1")?.textContent;
        if (title) document.title = title;
    }
    function scheduleRefresh() {
        if (!frame) frame = requestAnimationFrame(refreshLabels);
    }
    new MutationObserver(scheduleRefresh).observe(app.querySelector("#studio-main-tabs") || app,
        {subtree:true, childList:true, characterData:true});

    function filterOptions() {
        const input = normalize(search.value);
        for (const row of rows) {
            const matches = [...row.querySelectorAll("button")].some(option => {
                const code = option.dataset.locale;
                return normalize([names[code], aliases[code], code, row.value].join(" ")).includes(input);
            });
            row.hidden = !matches;
        }
        empty.hidden = rows.some(row => !row.hidden);
    }

    const supportsPopover = typeof panel.showPopover === "function";
    if (!supportsPopover) panel.removeAttribute("popover");

    function positionPanel() {
        if (panel.hidden) return;
        const anchor = trigger.getBoundingClientRect();
        const bounds = document.documentElement;
        const gutter = 12;
        const width = panel.getBoundingClientRect().width;
        const alignedLeft = rtl.includes(locale) ? anchor.left : anchor.right - width;
        const left = Math.max(gutter, Math.min(alignedLeft, bounds.clientWidth - width - gutter));
        const below = bounds.clientHeight - anchor.bottom - gutter;
        const above = anchor.top - gutter;
        const opensAbove = below < 235 && above > below;
        panel.style.left = left + "px";
        panel.style.top = opensAbove ? "auto" : anchor.bottom + "px";
        panel.style.bottom = opensAbove ? bounds.clientHeight - anchor.top + "px" : "auto";
        panel.style.maxHeight = Math.max(0, opensAbove ? above : below) + "px";
    }

    function setOpen(open) {
        if (panel.hidden === !open) return;
        trigger.setAttribute("aria-expanded", String(open));
        if (open) {
            panel.hidden = false;
            if (supportsPopover) panel.showPopover();
            positionPanel();
            return;
        }
        if (supportsPopover) panel.hidePopover();
        panel.hidden = true;
        pinned = false;
        search.value = "";
        list.scrollTop = 0;
        filterOptions();
    }

    window.addEventListener("resize", positionPanel, {passive:true});
    window.addEventListener("scroll", positionPanel, {passive:true});

    function select(next) {
        locale = Object.hasOwn(names, next) ? next : "zh-CN";
        module.changeLocale(locale);
        document.documentElement.lang = locale;
        app.setAttribute("dir", rtl.includes(locale) ? "rtl" : "ltr");
        name.textContent = names[locale];
        const labels = copy[locale];
        trigger.setAttribute("aria-label", labels.menu + " · " + names[locale]);
        panel.setAttribute("aria-label", labels.menu);
        search.placeholder = labels.search;
        search.setAttribute("aria-label", labels.search);
        empty.textContent = labels.empty;
        for (const option of options) {
            option.setAttribute("aria-pressed", String(option.dataset.locale === locale));
        }
        scheduleRefresh();
        try { localStorage.setItem(key, locale); } catch {}
    }

    let stored;
    try { stored = localStorage.getItem(key); } catch {}
    select(stored);

    menu.addEventListener("pointerenter", event => {
        if (event.pointerType === "mouse") setOpen(true);
    });
    menu.addEventListener("pointerleave", event => {
        if (event.pointerType === "mouse" && !pinned && !panel.contains(document.activeElement)) setOpen(false);
    });
    menu.addEventListener("focusout", event => {
        if (event.relatedTarget && !menu.contains(event.relatedTarget)) setOpen(false);
    });
    document.addEventListener("pointerdown", event => {
        if (!menu.contains(event.target)) setOpen(false);
    });
    trigger.addEventListener("click", () => {
        if (pinned) return setOpen(false);
        pinned = true;
        setOpen(true);
    });
    search.addEventListener("input", filterOptions);
    menu.addEventListener("keydown", event => {
        if (event.key === "Escape" && !panel.hidden) {
            event.preventDefault();
            setOpen(false);
            trigger.focus();
        } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)
                   && (event.target !== search || event.key.startsWith("Arrow"))) {
            event.preventDefault();
            setOpen(true);
            const visible = options.filter(option => !option.closest("li").hidden);
            if (!visible.length) return;
            const focused = visible.indexOf(document.activeElement);
            const last = visible.length - 1;
            const next = event.key === "Home" ? 0 : event.key === "End" ? last :
                event.key === "ArrowDown" ? (focused + 1) % visible.length :
                focused <= 0 ? last : focused - 1;
            visible[next].focus();
        }
    });
    for (const option of options) {
        option.addEventListener("click", () => {
            select(option.dataset.locale);
            setOpen(false);
            trigger.focus();
        });
    }
}
