// Pure UI policy for the level-processing controls. Keep this free of DOM
// access so the mode/toggle matrix can be checked independently.
export function levelOptionState(mode, waveformLoaded) {
  return {
    safetyDisabled: false,
    previewGainDisabled: mode !== "original" || !waveformLoaded,
  };
}
