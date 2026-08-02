import { useEffect, useRef, useState, type ReactNode } from 'react';
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

/* Each light is the first letter of what it does, so the word can grow out of the
   circle rather than appearing next to it - "r" is already the r of "room". */
const LETTERS = [
  { key: 'rooms',   letter: 'r', rest: 'oom',   label: 'rooms - play with other people' },
  { key: 'theme',   letter: 't', rest: 'heme',  label: 'theme - light dark. hold for more' },
  { key: 'reverse', letter: 's', rest: 'witch', label: 'switch - only words starting with r t s' },
] as const;

const LONG_PRESS_MS = 400;

/** How long the lights stay spelled out after one is pressed. */
const LABEL_MS = 3000;

/* The skin is called `aqua` everywhere it is stored - the attribute on <html>, the
   localStorage value, the ?skin= parameter, every selector in the stylesheet. Only
   the word on the button changes, because renaming the identifier would invalidate
   every stored preference for the sake of a label. */
const SKIN_LABEL = { aqua: 'bubbly', flat: 'flat' } as const;

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

  /* Press any light and all three say what they are for three seconds.
     After the press, never instead of it - the dots are the only labelling these
     controls have, and a first-time tap that explained itself but did nothing would
     be worse than one that does the thing. So the click lands, and the answer to
     "what did I just press?" arrives immediately afterwards. */
  const [labelled, setLabelled] = useState(false);
  const labelTimer = useRef<number | null>(null);

  const flash = () => {
    setLabelled(true);
    if (labelTimer.current !== null) clearTimeout(labelTimer.current);
    labelTimer.current = window.setTimeout(() => setLabelled(false), LABEL_MS);
  };

  useEffect(() => () => {
    if (labelTimer.current !== null) clearTimeout(labelTimer.current);
  }, []);

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

  /* A panel opened by holding a light is dismissed by touching anything else.
     There is no close button and there shouldn't be: it was opened by a gesture, so
     it should close by one, and on a phone the nearest thing to "put it away" is
     tapping the conversation you wanted to get back to. */
  const group = useRef<HTMLDivElement>(null);
  const open = appearance.open || !!roomBar;

  // Held in a ref so the listener below can be attached once per open rather than
  // re-attached on every render: both callbacks arrive fresh each time.
  const dismiss = useRef<() => void>(() => {});
  dismiss.current = () => {
    if (appearance.open) appearance.toggleOpen();
    if (roomBar) onHoldRooms?.();
  };

  useEffect(() => {
    if (!open) return;
    const away = (e: Event) => {
      if (!group.current?.contains(e.target as Node)) dismiss.current();
    };
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') dismiss.current();
    };
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', key);
    return () => {
      document.removeEventListener('pointerdown', away);
      document.removeEventListener('keydown', key);
    };
  }, [open]);

  return (
    <div className="rts-header-group" ref={group}>
      <div className={`rts-header${labelled ? ' is-labelled' : ''}`}
           onPointerDown={onDragStart}>
        {LETTERS.map(({ key, letter, rest, label }) => {
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
                flash();
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
              {/* The rest of the word, clipped to nothing until a press. Kept in the
                  DOM rather than added on demand so the pill has a real width to
                  animate towards - there is no transition from a circle to `auto`. */}
              <span className="rts-toggle-rest" aria-hidden="true">{rest}</span>
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
                {SKIN_LABEL[s]}
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
