/**
 * Dark mode, following ryOS (src/stores/useThemeStore.ts).
 *
 * The preference is tri-state, not a boolean: `system` is a real, *default*
 * choice that tracks the OS, and `light` / `dark` are explicit overrides. That
 * distinction is the whole point - a boolean can't tell "the user wants light"
 * apart from "the user hasn't said, and the OS is light right now", so it can
 * never follow the OS when the OS changes.
 *
 * What ryOS does NOT do, and neither do we any more: dim the wallpaper. Dark
 * mode repaints the chrome; the desktop is the user's picture and stays as
 * chosen. A dark panel is made dark by its own fill, not by draining the image
 * behind it.
 */

export type DarkModePreference = 'system' | 'light' | 'dark';

export const DARK_MODE_KEY = 'rts.darkMode';

export function isDarkModePreference(v: string | null): v is DarkModePreference {
  return v === 'system' || v === 'light' || v === 'dark';
}

export function initialDarkPreference(): DarkModePreference {
  const saved = localStorage.getItem(DARK_MODE_KEY);
  return isDarkModePreference(saved) ? saved : 'system';
}

export function systemPrefersDark(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return false;
  }
}

/** Resolve a preference to the boolean the CSS actually needs. */
export function effectiveDark(pref: DarkModePreference): boolean {
  if (pref === 'dark') return true;
  if (pref === 'light') return false;
  return systemPrefersDark();
}

/**
 * Watch the OS setting. The callback fires only while the preference is
 * `system` - an explicit override always wins, so there's no point re-rendering
 * for a change we're deliberately ignoring.
 */
export function watchSystemDark(onChange: (isDark: boolean) => void): () => void {
  if (typeof window === 'undefined' || !window.matchMedia) return () => {};
  let query: MediaQueryList;
  try {
    query = window.matchMedia('(prefers-color-scheme: dark)');
  } catch {
    return () => {};
  }
  const listener = (e: MediaQueryListEvent) => onChange(e.matches);
  if (typeof query.addEventListener === 'function') {
    query.addEventListener('change', listener);
    return () => query.removeEventListener('change', listener);
  }
  // Safari < 14
  query.addListener(listener);
  return () => query.removeListener(listener);
}
