import './header.css';

/**
 * The logo is the control panel. Each letter of "rts" is a toggle:
 *
 *   r — reverser.   flips the letter rule: r/t/s go from banned to mandatory.
 *   t — theme.      light <-> dark.
 *   s — see.        shows the AI's train of thought.
 *
 * An active toggle turns purple. This replaces the old standalone toggle buttons.
 */

export type Toggle = { on: boolean; toggle: () => void };

interface HeaderProps {
  reverse: Toggle;   // r
  theme: Toggle;     // t
  thoughts: Toggle;  // s
}

const LETTERS: Array<{ key: keyof HeaderProps; letter: string; label: string }> = [
  { key: 'reverse',  letter: 'r', label: 'reverser — only r/t/s words are legal' },
  { key: 'theme',    letter: 't', label: 'theme — light / dark' },
  { key: 'thoughts', letter: 's', label: 'see the train of thought' },
];

function Header(props: HeaderProps) {
  return (
    <div className="rts-header">
      {LETTERS.map(({ key, letter, label }) => {
        const { on, toggle } = props[key];
        return (
          <button
            key={letter}
            type="button"
            className={`rts-toggle${on ? ' is-on' : ''}`}
            onClick={toggle}
            aria-pressed={on}
            aria-label={label}
            title={label}
          >
            <span>{letter}</span>
          </button>
        );
      })}
    </div>
  );
}

export default Header;
