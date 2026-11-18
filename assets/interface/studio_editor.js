let currentEditor;

function mountEditor() {
    const panel = element.querySelector(".studio-wave-editor");
    if (!panel || panel === currentEditor) return;
    currentEditor = panel;
    const canvas = panel.querySelector("canvas");
    const ctx = canvas.getContext("2d");
    const player = panel.querySelector("audio");
    const startInput = panel.querySelector("[data-range=start]");
    const endInput = panel.querySelector("[data-range=end]");
    const comparisons = [...panel.querySelectorAll("[data-version]")];
    const total = Number(panel.dataset.length);
    const peaks = panel.dataset.peaks.split(",").map(Number);
    let anchor = null;
    let version = "a";
    let nextPosition = Number(panel.dataset.start);
    let resume = false;

    const clamp = value => Math.min(total, Math.max(0, value));
    const displayTime = value => Number(clamp(value).toFixed(3)).toString();
    const setRange = (start, end) => {
        startInput.value = displayTime(start);
        endInput.value = end >= total ? String(total) : displayTime(end);
        draw();
    };
    const fromPointer = event => {
        const rect = canvas.getBoundingClientRect();
        return clamp((event.clientX - rect.left) / rect.width * total);
    };
    const range = () => [Number(startInput.value), Number(endInput.value)];

    function draw() {
        const w = canvas.width, h = canvas.height;
        const [start, end] = range();
        ctx.clearRect(0, 0, w, h);
        ctx.fillStyle = "#4a7fff40";
        ctx.fillRect(start / total * w, 0, (end - start) / total * w, h);
        const color = getComputedStyle(panel).color;
        ctx.fillStyle = color;
        const stride = w / peaks.length;
        for (const [index, peak] of peaks.entries()) {
            const height = Math.max(1, peak / 100 * h * 0.89);
            ctx.fillRect(index * stride, (h - height) / 2, Math.max(1, stride - 1), height);
        }
        ctx.fillStyle = "#5388fd";
        ctx.fillRect(player.currentTime / total * w, 0, 2, h);
    }

    function choose(next, position) {
        const url = panel.dataset[next];
        if (!url) return;
        const [start, end] = range();
        nextPosition = position >= start && position < end ? position : start;
        resume = !player.paused;
        version = next;
        player.src = url;
        for (const button of comparisons)
            button.setAttribute("aria-pressed", String(button.dataset.version === version));
    }

    canvas.addEventListener("pointerdown", event => {
        if (event.button !== 0) return;
        canvas.setPointerCapture(event.pointerId);
        player.pause();
        anchor = fromPointer(event);
    });
    canvas.addEventListener("pointermove", event => {
        if (anchor === null) return;
        const edge = Math.min(anchor + 120, Math.max(anchor - 120, fromPointer(event)));
        setRange(Math.min(anchor, edge), Math.max(anchor, edge));
    });
    canvas.addEventListener("pointerup", event => {
        if (anchor === null) return;
        const position = fromPointer(event);
        if (Math.abs(position - anchor) < 0.03) {
            const first = Math.min(position, Math.max(0, total - 1));
            setRange(first, first + 10);
        }
        anchor = null;
        if (player.readyState) player.currentTime = Number(startInput.value);
        else nextPosition = Number(startInput.value);
    });
    canvas.addEventListener("pointercancel", () => { anchor = null; });
    for (const input of [startInput, endInput]) input.addEventListener("input", draw);
    for (const button of comparisons)
        button.addEventListener("click", () => {
            if (button.dataset.version !== version) choose(button.dataset.version, player.currentTime);
        });

    player.addEventListener("loadedmetadata", () => {
        player.currentTime = clamp(nextPosition);
        if (resume) player.play().catch(() => {});
        draw();
    });
    player.addEventListener("play", () => {
        const [start, end] = range();
        if (player.currentTime < start || player.currentTime >= end) player.currentTime = start;
    });
    player.addEventListener("timeupdate", () => {
        const [, end] = range();
        if (end > 0 && player.currentTime >= end) player.pause();
        draw();
    });
    setRange(Number(panel.dataset.start), Number(panel.dataset.end));
    choose("a", nextPosition);
    translateEditor();
}

function translateEditor() {
    if (!currentEditor || !currentEditor.isConnected) return;
    const language = document.documentElement.lang;
    const copy = language === "zh-TW"
        ? ["起點（秒）", "終點（秒）", "A · 原版", "B · 重做版", "試聽所選片段", "拖曳波形選段，也可以輸入起迄秒數。"]
        : language.startsWith("zh") || !language
          ? ["起点（秒）", "终点（秒）", "A · 原版", "B · 重做版", "试听所选片段", "拖动波形选段，也可以输入起止秒数。"]
          : ["Start (s)", "End (s)", "A · Original", "B · Redo", "Listen to selection", "Drag on the waveform or enter start and end times."];
    for (const [index, key] of ["start", "end", "original", "candidate"].entries())
        currentEditor.querySelector('[data-copy="' + key + '"]').textContent = copy[index];
    currentEditor.querySelector("[data-copy=hint]").textContent = copy[5];
    currentEditor.querySelector("audio").setAttribute("aria-label", copy[4]);
}

watch("value", mountEditor);
new MutationObserver(translateEditor).observe(document.documentElement, {
    attributes: true, attributeFilter: ["lang"],
});
mountEditor();

