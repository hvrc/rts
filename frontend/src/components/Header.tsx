import { useRef, type ReactNode } from 'react';
import './header.css';
import { ACCENT_ORDER, accentSwatch, type AccentId } from '../lib/accent';
import type { DarkModePreference } from '../lib/darkMode';

/**
 * The logo is the control panel. Each letter of "rts" is a toggle:
 *
 *   r - rooms.      swaps the chat for the lobby, and back.
 *   t - theme.      light <-> dark.  hold it for the appearance strip.
 *   s - switch.     flips the letter rule: r/t/s go from banned to mandatory.
 *
 * `s` used to show the train of thought and `r` used to be the switch. The train of
 * thought is still in the codebase, and still drawn if anything ever turns it back on,
 * but nothing does: it was the slowest field the model wrote and it was being generated
 * on every turn for an animation almost nobody opened. Rooms took the letter it left.
 *
 * An active toggle turns purple (or picks up the accent's gloss under the Aqua
 * skin). Appearance - skin and accent - hangs off a long press on `t` rather
 * than a fourth button, because a fourth button stops the logo spelling "rts".
 */

export type Toggle = { on: boolean; toggle: () => void };

interface HeaderProps {
  rooms: Toggle;     // r
  theme: Toggle;     // t
  reverse: Toggle;   // s

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

  /** Whose go it is, when there's a room and more than one of you. */
  turn?: ReactNode;

  /** The room strip: revealed by holding `r`, the same way `t` reveals appearance. */
  roomBar?: ReactNode;
  onHoldRooms?: () => void;
}

const LETTERS = [
  { key: 'rooms',   letter: 'r', label: 'rooms - play with other people' },
  { key: 'theme',   letter: 't', label: 'theme - light / dark. hold for appearance' },
  { key: 'reverse', letter: 's', label: 'switch - only r/t/s words are legal' },
] as const;

const LONG_PRESS_MS = 400;

function Header({ rooms, reverse, theme, appearance, onDragStart, clock, turn,
                  roomBar, onHoldRooms }: HeaderProps) {
  const toggles = { rooms, reverse, theme };

  // Two letters do a second thing when held: `t` opens appearance, `r` opens the
  // room's settings. The timer fires the open; `fired` then swallows the click that
  // follows, so a hold never also runs the tap action underneath it.
  const holds: Partial<Record<string, () => void>> = {
    theme: appearance.toggleOpen,
    rooms: onHoldRooms,
  };

  const timer = useRef<number | null>(null);
  const fired = useRef(false);

  const startHold = (action: () => void) => () => {
    fired.current = false;
    timer.current = window.setTimeout(() => {
      fired.current = true;
      action();
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
          const hold = holds[key];
          return (
            <button
              key={letter}
              type="button"
              className={`rts-toggle rts-toggle--${letter}${on ? ' is-on' : ''}`}
              onClick={() => {
                if (hold && fired.current) {
                  fired.current = false;
                  return;
                }
                toggle();
              }}
              onPointerDown={hold && startHold(hold)}
              onPointerUp={hold && cancelHold}
              onPointerLeave={hold && cancelHold}
              onContextMenu={
                hold
                  ? (e) => {
                      e.preventDefault();
                      hold();
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
        {turn}
        {clock}
      </div>

      {roomBar}

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
