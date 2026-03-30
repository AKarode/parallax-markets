const COUNTRY_COLORS: Record<string, [number, number, number]> = {
  iran: [239, 68, 68],     // red
  usa: [59, 130, 246],     // blue
  saudi_arabia: [34, 197, 94], // green
  china: [234, 179, 8],    // yellow
  russia: [168, 85, 247],  // purple
  uae: [6, 182, 212],      // cyan
  india: [249, 115, 22],   // orange
  israel: [236, 72, 153],  // pink
};

export function influenceToColor(influence: string | null): [number, number, number, number] {
  if (!influence) return [30, 41, 59, 80]; // slate, low alpha
  const base = COUNTRY_COLORS[influence] ?? [148, 163, 184]; // gray fallback
  return [...base, 180];
}

export function threatToColor(threat: number): [number, number, number, number] {
  // 0 = green, 0.5 = yellow, 1 = red
  const r = Math.round(255 * Math.min(1, threat * 2));
  const g = Math.round(255 * Math.max(0, 1 - threat * 2));
  return [r, g, 0, Math.round(60 + threat * 140)];
}
