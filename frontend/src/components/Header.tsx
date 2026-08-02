import { useRef, type ReactNode } from 'react';
import './header.css';
import { ACCENT_ORDER, accentSwatch, type AccentId } from '../lib/accent';
import type { DarkModePreference } from '../lib/darkMode';

/**
 * The logo is the control panel. Each letter of "rts" is a toggle:
 *
 *   r - reverser.   flips the letter rule: r/t/s go from banned to mandatory.
 *   t - theme.      light <-> dark.  hold it for the appearance strip.
 *   s - see.        shows the AI's train of thought.
 *
 * An active toggle turns purple (or picks up the accent's gloss under the Aqua
 * skin). Appearance - skin and accent - hangs off a long press on `t` rather
 * than a fourth button, because a fourth button stops the logo spelling "rts".
 */

export type Toggle = { on: boolean; toggle: () => void };

interface HeaderProps {
  reverse: Toggle;   // r
  theme: Toggle;     // t
  thoughts: Toggle;  // s

  /** Appearance strip: revealed by holding `t`. */
  appearance: {
    open: boolean;
    toggleOpen: () => void;
    skin: 'aqua' | 'flat';
    setSkin: (skin: 'aqua' | 'flat') => void;
    accent: AccentId;
    setAccent: (accent: AccentId) => void;
    /** Live color sampled from the wallpaper; null until it resolves. */
    wallpaperAccent: string | null;
    darkPref: DarkModePreference;
    setDarkPref: (pref: DarkModePreference) => void;
  };

  /** The bar doubles as the window's drag handle. */
  onDragStart: (e: React.PointerEvent) => void;

  /** The turn clock. Owns the right end of the bar; the lights own the left. */
  clock?: ReactNode;
}

const LETTERS = [
  { key: 'reverse',  letter: 'r', label: 'reverser - only r/t/s words are legal' },
  { key: 'theme',    letter: 't', label: 'theme - light / dark. hold for appearance' },
  { key: 'thoughts', letter: 's', label: 'see the train of thought' },
] as const;

const LONG_PRESS_MS = 400;

function Header({ reverse, theme, thoughts, appearance, onDragStart, clock }: HeaderProps) {
  const toggles = { reverse, theme, thoughts };

  // A long press on `t` opens the appearance strip instead of flipping the
  // theme. The timer fires the open; `fired` then swallows the click that
  // follows, so a hold never also toggles light/dark.
  const timer = useRef<number | null>(null);
  const fired = useRef(false);

  const startHold = () => {
    fired.current = false;
    timer.current = window.setTimeout(() => {
      fired.current = true;
      appearance.toggleOpen();
    }, LONG_PRESS_MS);
  };

  const cancelHold = () => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };

  return (
    <div className="rts-header-group">
      <div className="rts-header" onPointerDown={onDragStart}>
        {LETTERS.map(({ key, letter, label }) => {
          const { on, toggle } = toggles[key];
          const isTheme = key === 'theme';
          return (
            <button
              key={letter}
              type="button"
              className={`rts-toggle rts-toggle--${letter}${on ? ' is-on' : ''}`}
              onClick={() => {
                if (isTheme && fired.current) {
                  fired.current = false;
                  return;
                }
                toggle();
              }}
              onPointerDown={isTheme ? startHold : undefined}
              onPointerUp={isTheme ? cancelHold : undefined}
              onPointerLeave={isTheme ? cancelHold : undefined}
              onContextMenu={
                isTheme
                  ? (e) => {
                      e.preventDefault();
                      appearance.toggleOpen();
                    }
                  : undefined
              }
              aria-pressed={on}
              aria-label={label}
              title={label}
            >
              <span>{letter}</span>
            </button>
          );
        })}
        <div className="rts-header-spacer" />
        {clock}
      </div>

      {appearance.open && (
        <div className="rts-appearance">
          <div className="rts-skins">
            {(['aqua', 'flat'] as const).map((s) => (
              <button
                key={s}
                type="button"
                className={`rts-skin${appearance.skin === s ? ' is-on' : ''}`}
                onClick={() => appearance.setSkin(s)}
                aria-pressed={appearance.skin === s}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Tri-state, like ryOS: `system` is the default and follows the OS;
              light and dark are explicit overrides that stop following it. */}
          <div className="rts-skins">
            {(['system', 'light', 'dark'] as const).map((p) => (
              <button
                key={p}
                type="button"
                className={`rts-skin${appearance.darkPref === p ? ' is-on' : ''}`}
                onClick={() => appearance.setDarkPref(p)}
                aria-pressed={appearance.darkPref === p}
              >
                {p}
              </button>
            ))}
          </div>

          <div className="rts-accents">
            {ACCENT_ORDER.map((id) => {
              const swatch = accentSwatch(id, appearance.wallpaperAccent);
              const isGradient = swatch.startsWith('conic-gradient');
              return (
                <button
                  key={id}
                  type="button"
                  className={`rts-swatch${appearance.accent === id ? ' is-on' : ''}`}
                  style={isGradient ? { backgroundImage: swatch } : { backgroundColor: swatch }}
                  onClick={() => appearance.setAccent(id)}
                  aria-pressed={appearance.accent === id}
                  aria-label={`accent - ${id}`}
                  title={id === 'wallpaper' ? 'wallpaper - sampled from the desktop' : id}
                />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default Header;
