// Pure trim math shared by the unified and per-track editors.
export function clampTime(value, duration) {
  return Math.max(0, Math.min(Number(value) || 0, duration));
}

// Number inputs display milliseconds, so their HTML max must be rounded up to
// the same precision. Otherwise a duration such as 244.750667 is rendered as
// 244.751 but rejected by the browser as being above the raw max value.
export function displayTimeLimit(duration) {
  const value = Number(duration);
  return Number.isFinite(value) && value >= 0 ? Math.ceil(value * 1000) / 1000 : 0;
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
