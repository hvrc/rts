import type { Rating as RatingValue } from '../lib/prefs';
import './rating.css';

/**
 * Thumbs on a bot word.
 *
 * The thing being rated is the *link* the bot played (peace -> war), not the word on
 * its own — "war" alone tells the bot nothing, but "from peace, it leapt to war" is a
 * taste it can learn. The chosen one turns purple, same language as the header toggles.
 */

interface RatingProps {
  value?: RatingValue;
  onRate: (rating: RatingValue) => void;
}

function Rating({ value, onRate }: RatingProps) {
  return (
    <div className="rts-rating">
      <button
        type="button"
        className={`rts-rate${value === 'like' ? ' is-on' : ''}`}
        onClick={() => onRate('like')}
        aria-pressed={value === 'like'}
        aria-label="good link — more like this"
        title="good link — more like this"
      >
        ↑
      </button>
      <button
        type="button"
        className={`rts-rate${value === 'dislike' ? ' is-on' : ''}`}
        onClick={() => onRate('dislike')}
        aria-pressed={value === 'dislike'}
        aria-label="weak link — less like this"
        title="weak link — less like this"
      >
        ↓
      </button>
    </div>
  );
}

export default Rating;
