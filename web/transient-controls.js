import { t } from "./i18n.js";

// Export-affecting DSP, deliberately separate from preview-only gain/limiter.
export class TransientControls {
  constructor(editor, state) {
    this.editor = editor;
    this.state = state;
    this.enabled = false;
    this.drive = 0;
    this.ready = false;
    this.panel = document.createElement("details");
    this.panel.className = "transient-panel";
    state.row.append(this.panel);
    this.draw();
  }

  boundsKey() { return JSON.stringify(this.editor.hooks.bounds(this.state.row)); }
  selected() { return this.state.row.querySelector("input[name=selectedFiles]").checked; }
  payload() { return { enabled: this.enabled, drive: this.drive }; }

  invalidate() {
    if (!this.enabled) return;
    this.ready = false;
    this.media = null;
    this.editor.swap(this.state, this.state.localCommitted);
    this.state.committed = this.state.localCommitted;
    this.draw();
  }

  checkBounds() {
    if (this.ready && this.bounds !== this.boundsKey()) this.invalidate();
  }

  async apply() {
    if (this.editor.busy || !this.selected()) return;
    for (const state of this.editor.states.values()) this.editor.close(state);
    const epoch = this.editor.epoch;
    const bounds = this.boundsKey(), drive = this.drive;
    this.editor.hooks.stop();
    const pending = this.editor.job("/api/peak-render", [{
      name: this.state.track.name, audio: this.state.track.audio,
      edits: this.editor.edits(this.state), transient: this.payload(),
      ...JSON.parse(bounds),
    }]);
    this.draw();
    try {
      const result = await pending;
      if (!result || epoch !== this.editor.epoch) return;
      // A trim may move during a render. Never install stale audio.
      if (bounds !== this.boundsKey() || drive !== this.drive || !this.enabled) return;
      this.media = result[0];
      this.bounds = bounds;
      this.ready = true;
      this.auditionAfter = true;
      this.state.committed = { ...this.media, image: this.state.localCommitted.image };
      this.editor.swap(this.state, this.state.committed);
      this.error = "";
    } catch (error) { this.error = error.message; }
    finally { this.draw(); }
  }

  listen(after) {
    this.checkBounds();
    if (!this.ready || this.editor.busy || !this.selected()) return;
    const audio = this.state.row.querySelector("audio");
    const bounds = this.editor.hooks.bounds(this.state.row);
    const position = audio.readyState >= 1 ? audio.currentTime : Number(audio.dataset.previewPosition || 0);
    const start = Math.max(bounds.start, Math.min(bounds.end - .001, position));
    this.editor.swap(this.state, { audio: after ? this.media.audio : this.media.beforeAudio,
      image: this.state.localCommitted.image });
    this.editor.hooks.audition(this.state.row, start, bounds.end);
    this.auditionAfter = after;
    this.draw();
  }

  draw() {
    const open = this.panel.open;
    this.panel.innerHTML = `<summary>${t("transientTitle")}${this.enabled ? " ✓" : ""}</summary>
      <p>${t("transientHelp")}</p>
      <label class="checkbox toggle-option"><input class="transient-enable" type="checkbox"><span>${t("transientEnable")}</span></label>
      <div class="transient-drive-row"><label>${t("transientDrive")} (dB)
        <input class="transient-drive" type="number" min="0" max="12" step="0.5"></label>
        <input class="transient-range" type="range" min="0" max="12" step="0.5" aria-label="${t("transientDrive")}"></div>
      <div class="peak-actions"><button class="secondary transient-apply" type="button">${t("transientApply")}</button>
        <button class="secondary transient-before" type="button">${t("transientBefore")}</button>
        <button class="secondary transient-after" type="button">${t("transientAfter")}</button></div>
      <p class="transient-status" role="status"></p>`;
    this.panel.open = open;
    const enable = this.panel.querySelector(".transient-enable");
    enable.checked = this.enabled;
    const blocked = this.editor.busy || !this.selected();
    enable.disabled = blocked;
    enable.addEventListener("change", () => {
      this.enabled = enable.checked;
      this.ready = false;
      this.error = "";
      if (!this.enabled) {
        this.state.committed = this.state.localCommitted;
        this.editor.swap(this.state, this.state.committed);
        this.draw();
      } else this.apply();
    });
    for (const input of this.panel.querySelectorAll(".transient-drive,.transient-range")) {
      input.value = this.drive;
      input.disabled = blocked || !this.enabled;
      input.addEventListener("input", () => {
        const value = Number(input.value);
        if (!input.value || !Number.isFinite(value) || value < 0 || value > 12) {
          input.setCustomValidity(t("transientInvalid")); return;
        }
        input.setCustomValidity("");
        this.drive = value;
        this.panel.querySelector(input.classList.contains("transient-range") ? ".transient-drive" : ".transient-range").value = value;
        // Keep focus while marking the rendered effect stale.
        if (this.ready) {
          this.editor.swap(this.state, this.state.localCommitted);
          this.state.committed = this.state.localCommitted;
        }
        this.ready = false;
        this.panel.querySelectorAll(".transient-before,.transient-after").forEach(b => b.disabled = true);
        this.panel.querySelector(".transient-status").textContent = t("transientStale");
      });
    }
    const apply = this.panel.querySelector(".transient-apply");
    apply.disabled = blocked || !this.enabled;
    apply.addEventListener("click", () => {
      if (this.panel.querySelector(".transient-drive").reportValidity()) this.apply();
    });
    for (const [selector, after] of [[".transient-before", false], [".transient-after", true]]) {
      const button = this.panel.querySelector(selector);
      button.disabled = blocked || !this.ready;
      button.setAttribute("aria-pressed", String(this.ready && this.auditionAfter === after));
      button.addEventListener("click", () => this.listen(after));
    }
    const stats = this.ready && this.media?.transientStats;
    this.panel.querySelector(".transient-status").textContent = this.error || (blocked && this.editor.busy ? t("peakBusy")
      : stats ? `${t("transientMaxReduction")}: ${stats.maxReduction.toFixed(1)} dB · ${t("transientLimitedTime")}: ${stats.limitedPercent.toFixed(1)}%`
      : this.enabled ? t("transientStale") : "");
  }
}
