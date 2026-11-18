// Reuse only the selection mask, never filenames, trims, gains or peak edits.
export function audibleSelection(tracks, threshold) {
  return tracks.map(({ peak }) => typeof peak === "number" && Number.isFinite(peak) && peak > threshold);
}

export function selectionForCount(previous, count, splitStereo) {
  if (previous?.splitStereo === splitStereo && previous.values?.length === count
      && previous.values.every((value) => typeof value === "boolean")) return [...previous.values];
  return Array(count).fill(true);
}
