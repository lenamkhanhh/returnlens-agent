/**
 * Utility for parsing and managing demo scale mode (?demo=1 or ?scale=1.35).
 * Wave 11: Scales UI to 125-150% (default 135% / 1.35) for 1080p video recording readability.
 */
export function resolveDemoScale(searchString?: string, storedScale?: string | null): number | null {
  const search = typeof searchString !== 'undefined'
    ? searchString
    : (typeof window !== 'undefined' ? window.location.search : '');
  const params = new URLSearchParams(search);
  const demoParam = params.get('demo');
  const scaleParam = params.get('scale');

  if (demoParam === '0' || demoParam === 'false') {
    return null;
  }
  if (scaleParam && !isNaN(parseFloat(scaleParam))) {
    const s = parseFloat(scaleParam);
    return s > 0 ? s : null;
  }
  if (demoParam && !isNaN(parseFloat(demoParam)) && parseFloat(demoParam) > 0 && parseFloat(demoParam) !== 1) {
    return parseFloat(demoParam);
  }
  if (demoParam === '1' || demoParam === 'true') {
    return 1.35; // Default 135% scaling for 1080p video recording per Wave 11
  }
  if (storedScale && !isNaN(parseFloat(storedScale))) {
    const s = parseFloat(storedScale);
    return s > 0 ? s : null;
  }
  return null;
}
