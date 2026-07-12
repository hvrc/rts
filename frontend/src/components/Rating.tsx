import type { Rating as RatingValue } from '../lib/prefs';
import './rating.css';

/**
 * Thumbs on a bot word — the original circles, back where they were: pinned to the two
 * right-hand corners of the bubble, same 20px pop-in as the "?" badge. Up top-right,
 * down bottom-right.
 *
 * What's rated is the *link* the bot played (peace -> war), not the word alone. "war"
 * on its own teaches it nothing; "from peace, it leapt to war, and I liked that" is a
 * taste it can act on.
 *
 * Must be rendered inside the bubble's `position: relative` wrapper — these are
 * absolutely positioned against it, exactly like the question mark.
 */

interface RatingProps {
  value?: RatingValue;
  onRate: (rating: RatingValue) => void;
}

function Rating({ value, onRate }: RatingProps) {
  return (
    <>
      <button
        type="button"
        className={`rating-circle like-circle${value === 'like' ? ' selected' : ''}`}
        onClick={(e) => { e.stopPropagation(); onRate('like'); }}
        aria-pressed={value === 'like'}
        aria-label="good link — more like this"
        title="good link — more like this"
      />
      <button
        type="button"
        className={`rating-circle dislike-circle${value === 'dislike' ? ' selected' : ''}`}
        onClick={(e) => { e.stopPropagation(); onRate('dislike'); }}
        aria-pressed={value === 'dislike'}
        aria-label="weak link — less like this"
        title="weak link — less like this"
      />
    </>
  );
}

export default Rating;
