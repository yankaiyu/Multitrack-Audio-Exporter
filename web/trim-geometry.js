// Pure trim math shared by the unified and per-track editors.
export function clampTime(value, duration) {
  return Math.max(0, Math.min(Number(value) || 0, duration));
}

export function normalizeTrimRange(startValue, endValue, duration, changed = "") {
  let start = clampTime(startValue, duration);
  let end = clampTime(endValue, duration);
  if (changed === "start" && start >= end) end = Math.min(duration, start + 0.001);
  if (changed === "end" && end <= start) start = Math.max(0, end - 0.001);
  return { start, end };
}

export function timeAtPointer(clientX, bounds, duration) {
  if (!bounds?.width || !duration) return 0;
  return clampTime((clientX - bounds.left) / bounds.width * duration, duration);
}
