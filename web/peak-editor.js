import { $, api } from "./core.js";
import { t, currentLanguage } from "./i18n.js";

// Separate editing state from trim, selection and preview-only volume settings.
export class PeakEditor {
  constructor(hooks) {
    this.hooks = hooks;
    this.states = new Map();
    this.epoch = 0;
    this.busy = false;
    $("#detect-peaks").addEventListener("click", () => this.detect());
    window.addEventListener("resize", () => this.layout());
    document.addEventListener("languagechange", () => this.refresh());
  }

  reset() {
    if (this.activeJob) api("/api/cancel", { method: "POST", body: JSON.stringify({ job: this.activeJob }) }).catch(() => {});
    this.activeJob = null;
    this.epoch++;
    this.busy = false;
    this.states.clear();
    $("#peak-tools").classList.add("hidden");
    $("#peak-status").textContent = "";
    $("#detect-peaks").disabled = false;
  }

  attach(tracks) {
    for (const track of tracks) {
      const row = this.hooks.row(track.name);
      const state = { track, row, candidates: [], committed: track, draft: null, active: null };
      this.states.set(track.name, state);
      const layer = document.createElement("div");
      layer.className = "peak-layer";
      row.querySelector(".wave-image-wrap").append(layer);
      const panel = document.createElement("div");
      panel.className = "peak-panel hidden";
      row.append(panel);
      const badge = document.createElement("span");
      badge.className = "peak-badge";
      row.querySelector(".wave-name").append(badge);
      row.querySelector(".wave-image").addEventListener("load", () => this.layout());
    }
    $("#peak-tools").classList.remove("hidden");
    this.refresh();
  }

  edits(state, draft = null) {
    return state.candidates.filter((item) => item.applied && item !== state.active)
      .map(({ start, end, db }) => ({ start, end, db }))
      .concat(draft ? [{ start: draft.start, end: draft.end, db: draft.db }]
        : state.active?.applied ? [{ start: state.active.start, end: state.active.end, db: state.active.db }] : []);
  }

  payload() {
    return Object.fromEntries([...this.states].map(([name, state]) => [name,
      state.candidates.filter((item) => item.applied).map(({ start, end, db }) => ({ start, end, db }))]));
  }

  async job(path, tracks) {
    const epoch = this.epoch;
    this.busy = true;
    $("#detect-peaks").disabled = true;
    document.querySelectorAll(".peak-flag").forEach((button) => { button.disabled = true; });
    try {
      const { job } = await api(path, { method: "POST", body: JSON.stringify({ tracks, language: currentLanguage() }) });
      if (epoch !== this.epoch) { await api("/api/cancel", { method: "POST", body: JSON.stringify({ job }) }); return null; }
      this.activeJob = job;
      while (epoch === this.epoch) {
        const data = await api(`/api/job/${job}`);
        if (epoch !== this.epoch) return null;
        $("#peak-status").textContent = data.progressLabel || t("peakBusy");
        if (data.status === "done") return data.results;
        if (data.status !== "running") throw new Error(data.log || t("peakAnalysisFailed"));
        await new Promise((resolve) => setTimeout(resolve, 300));
      }
      return null;
    } catch (error) {
      if (epoch !== this.epoch) return null;
      throw error;
    } finally {
      if (epoch === this.epoch) {
        this.activeJob = null;
        this.busy = false;
        $("#detect-peaks").disabled = false;
        document.querySelectorAll(".peak-flag").forEach((button) => { button.disabled = button.closest(".wave-track").classList.contains("is-deselected"); });
      }
    }
  }

  async detect() {
    if (this.busy) return;
    const selected = [...this.states.values()].filter(({ row }) => row.querySelector("input[name=selectedFiles]").checked);
    if (!selected.length) { $("#peak-status").textContent = t("selectAtLeastOneTrack"); return; }
    // Discard only unconfirmed drafts; retain all previously applied edits.
    for (const state of this.states.values()) this.close(state);
    this.hooks.stop();
    try {
      const results = await this.job("/api/peak-detect", selected.map(({ track, row }) => ({
        name: track.name, audio: track.audio, ...this.hooks.bounds(row),
      })));
      if (!results) return;
      for (const result of results) {
        const state = this.states.get(result.name);
        const applied = state.candidates.filter((c) => c.applied);
        state.candidates = [...applied, ...result.candidates.filter((c) => !applied.some((a) => c.start < a.end && c.end > a.start))];
      }
      $("#peak-status").textContent = results.some((r) => r.candidates.length) ? t("peakReviewHelp") : t("peakNoCandidates");
      this.refresh();
    } catch (error) { $("#peak-status").textContent = error.message; }
  }

  swap(state, media) {
    this.hooks.stop();
    const audio = state.row.querySelector(".track-preview-audio");
    delete audio.dataset.auditionEnd;
    audio.src = media.audio;
    audio.load();
    state.row.querySelector(".wave-image").src = media.image;
  }

  close(state) {
    if (state.active) this.swap(state, state.committed);
    state.active = state.draft = null;
    state.row.querySelector(".peak-panel").classList.add("hidden");
    this.regions(state);
  }

  refresh() {
    for (const state of this.states.values()) {
      const layer = state.row.querySelector(".peak-layer");
      layer.replaceChildren();
      const applied = state.candidates.filter((c) => c.applied).length;
      const pending = state.candidates.filter((c) => !c.applied && !c.dismissed).length;
      state.row.querySelector(".peak-badge").textContent = state.candidates.length
        ? ` · ${t("peakPending")}: ${pending} · ${t("peakApplied")}: ${applied}` : "";
      for (const candidate of state.candidates) {
        if (candidate.dismissed) continue;
        const marker = document.createElement("button");
        marker.type = "button";
        marker.className = `peak-flag${candidate.applied ? " applied" : ""}`;
        marker.style.left = `${Math.max(0, Math.min(100, candidate.time / state.track.duration * 100))}%`;
        marker.title = `${t(candidate.applied ? "peakApplied" : "peakSuspect")} · ${candidate.time.toFixed(3)} s`;
        marker.textContent = candidate.applied ? "✓" : "!";
        marker.disabled = this.busy || state.row.classList.contains("is-deselected");
        marker.addEventListener("click", () => {
          if (this.busy || state.row.classList.contains("is-deselected")) return;
          for (const other of this.states.values()) this.close(other);
          state.active = candidate;
          state.draft = { ...candidate };
          this.panel(state);
        });
        layer.append(marker);
      }
      if (state.active) this.panel(state);
      this.regions(state);
    }
    this.layout();
  }

  regions(state) {
    const layer = state.row.querySelector(".peak-layer");
    layer.querySelectorAll(".peak-highlight").forEach((node) => node.remove());
    const edits = this.edits(state, state.draft);
    for (const edit of edits) {
      const region = document.createElement("span");
      region.className = "peak-highlight";
      Object.assign(region.style, { left: `${edit.start / state.track.duration * 100}%`,
        width: `${(edit.end - edit.start) / state.track.duration * 100}%` });
      layer.prepend(region);
    }
  }

  layout() {
    for (const { row } of this.states.values()) {
      const image = row.querySelector(".wave-image"), layer = row.querySelector(".peak-layer");
      const a = image.getBoundingClientRect(), b = image.parentElement.getBoundingClientRect();
      Object.assign(layer.style, { left: `${a.left - b.left}px`, top: `${a.top - b.top}px`, width: `${a.width}px`, height: `${a.height}px` });
    }
  }

  panel(state) {
    const panel = state.row.querySelector(".peak-panel");
    const draft = state.draft;
    panel.classList.remove("hidden");
    panel.innerHTML = `<strong>${t("peakSuspect")} · ${state.active.time.toFixed(3)} s</strong>
      <p>${t("peakReviewHelp")}</p><p class="peak-export-note">${t("peakExportHelp")}</p>
      <div class="peak-fields">
        <label>${t("trackStart")} (s)<input class="peak-start" type="number" min="0" step="0.001" value="${draft.start.toFixed(3)}"></label>
        <label>${t("trackEnd")} (s)<input class="peak-end" type="number" min="0" step="0.001" value="${draft.end.toFixed(3)}"></label>
        <label>${t("peakReduction")} (dB)<input class="peak-db" type="number" min="-60" max="0" step="0.1" value="${draft.db}"><input class="peak-gain-range" type="range" min="-60" max="0" step="0.1" value="${draft.db}" aria-label="${t("peakReduction")}"></label>
      </div><div class="peak-actions"></div><p class="peak-message" role="status"></p>`;
    const actions = panel.querySelector(".peak-actions");
    const read = () => {
      const start = Number(panel.querySelector(".peak-start").value);
      const end = Number(panel.querySelector(".peak-end").value);
      const db = Number(panel.querySelector(".peak-db").value);
      if (![start, end, db].every(Number.isFinite) || start < 0 || end <= start || end > state.track.duration + .001 || db < -60 || db > 0)
        throw new Error(t("peakInvalidEdits"));
      Object.assign(draft, { start, end: Math.min(end, state.track.duration), db });
      return draft;
    };
    const near = () => {
      const bounds = this.hooks.bounds(state.row);
      this.hooks.audition(state.row, Math.max(bounds.start, draft.start - 2), Math.min(bounds.end, draft.end + 2));
    };
    const render = async () => {
      read();
      this.hooks.stop();
      const result = await this.job("/api/peak-render", [{ name: state.track.name, audio: state.track.audio, edits: this.edits(state, draft) }]);
      return result?.[0];
    };
    const action = (key, callback) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "secondary"; button.textContent = t(key);
      button.addEventListener("click", async () => {
        if (this.busy) return;
        panel.querySelectorAll("button,input").forEach((c) => c.disabled = true);
        try { await callback(); }
        catch (error) { panel.querySelector(".peak-message").textContent = error.message; }
        finally { panel.querySelectorAll("button,input").forEach((c) => c.disabled = false); }
      });
      actions.append(button);
    };
    action("peakListenOriginal", () => { read(); this.swap(state, state.track); near(); });
    action("peakListenEdited", async () => { const media = await render(); if (media) { this.swap(state, media); near(); } });
    action("peakApply", async () => {
      const media = await render();
      if (!media) return;
      Object.assign(state.active, draft, { applied: true, dismissed: false });
      state.committed = media;
      this.close(state); this.refresh();
    });
    action(state.active.applied ? "peakUndo" : "peakKeep", async () => {
      if (state.active.applied) {
        const remaining = state.candidates.filter((c) => c.applied && c !== state.active);
        const result = remaining.length ? await this.job("/api/peak-render", [{ name: state.track.name, audio: state.track.audio, edits: remaining }]) : [state.track];
        if (!result) return;
        state.committed = result[0];
      }
      state.active.applied = false;
      state.active.dismissed = true;
      this.close(state); this.refresh();
    });
    action("peakCancel", () => { this.close(state); this.refresh(); });
    // A zoomed range editor makes even short spikes draggable without changing trims.
    const zoom = document.createElement("div");
    zoom.className = "peak-zoom";
    const low = Math.max(0, state.active.time - 1), high = Math.min(state.track.duration, state.active.time + 1);
    zoom.innerHTML = `<span class="peak-region"></span><button type="button" class="peak-edge start">◀</button><button type="button" class="peak-edge end">▶</button>`;
    panel.querySelector(".peak-fields").after(zoom);
    const position = () => {
      const left = Math.max(0, Math.min(100, (draft.start - low) / (high - low) * 100));
      const right = Math.max(0, Math.min(100, (draft.end - low) / (high - low) * 100));
      zoom.querySelector(".start").style.left = `${left}%`;
      zoom.querySelector(".end").style.left = `${right}%`;
      Object.assign(zoom.querySelector(".peak-region").style, { left: `${left}%`, width: `${right - left}%` });
      this.regions(state);
    };
    for (const edge of zoom.querySelectorAll("button")) {
      edge.title = t(edge.classList.contains("start") ? "trackStart" : "trackEnd");
      edge.addEventListener("pointerdown", (event) => { if (!this.busy) { edge.setPointerCapture(event.pointerId); event.preventDefault(); } });
      edge.addEventListener("pointermove", (event) => {
        if (!edge.hasPointerCapture(event.pointerId) || this.busy) return;
        const bounds = zoom.getBoundingClientRect();
        const value = low + Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)) * (high - low);
        if (edge.classList.contains("start")) draft.start = Math.min(value, draft.end - .001);
        else draft.end = Math.max(value, draft.start + .001);
        panel.querySelector(".peak-start").value = draft.start.toFixed(3);
        panel.querySelector(".peak-end").value = draft.end.toFixed(3);
        position();
      });
      edge.addEventListener("pointerup", (event) => { if (edge.hasPointerCapture(event.pointerId)) edge.releasePointerCapture(event.pointerId); });
    }
    panel.querySelectorAll("input").forEach((input) => input.addEventListener("input", () => {
      if (input.classList.contains("peak-gain-range")) panel.querySelector(".peak-db").value = input.value;
      if (input.classList.contains("peak-db")) panel.querySelector(".peak-gain-range").value = input.value;
      try { read(); position(); panel.querySelector(".peak-message").textContent = ""; }
      catch (error) { panel.querySelector(".peak-message").textContent = error.message; }
    }));
    position();
  }
}
