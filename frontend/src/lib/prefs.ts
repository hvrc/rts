/**
 * Learned taste, and who you are.
 *
 * A rating is on a *link* — the leap the bot made (`from -> to`), not a bare word.
 * Thumbs-up means "more leaps like that"; thumbs-down means "fewer". Both persist
 * across games, and ride along on every turn so the bot can weigh them.
 *
 * This lives in the browser rather than a database on purpose: the taste is yours,
 * it survives backend restarts and deploys, and it needs no storage layer to exist.
 */

const GAME_KEY = 'rts.gameId';
const PREFS_KEY = 'rts.prefs';

const MAX_PER_LIST = 30; // the backend caps too; this keeps the request small

export type Link = { from: string; to: string };
export type Rating = 'like' | 'dislike';

type Pair = [string, string];
type Prefs = { liked: Pair[]; disliked: Pair[] };

/** One game per browser. Without this, everyone on the site shares one chain. */
export function gameId(): string {
  let id = localStorage.getItem(GAME_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(GAME_KEY, id);
  }
  return id;
}

export function loadPrefs(): Prefs {
  try {
    const raw = JSON.parse(localStorage.getItem(PREFS_KEY) || '{}');
    return {
      liked: sane(raw.liked),
      disliked: sane(raw.disliked),
    };
  } catch {
    return { liked: [], disliked: [] };
  }
}

/**
 * Record a rating. A link lives in exactly one list, so re-rating it the other way
 * moves it, and rating it the same way twice is a no-op.
 */
export function ratePair(link: Link, rating: Rating): Prefs {
  const pair: Pair = [link.from.toLowerCase(), link.to.toLowerCase()];
  const prefs = loadPrefs();

  const drop = (list: Pair[]) => list.filter(([a, b]) => !(a === pair[0] && b === pair[1]));
  const liked = drop(prefs.liked);
  const disliked = drop(prefs.disliked);

  if (rating === 'like') liked.push(pair);
  else disliked.push(pair);

  const next: Prefs = {
    liked: liked.slice(-MAX_PER_LIST),
    disliked: disliked.slice(-MAX_PER_LIST),
  };
  localStorage.setItem(PREFS_KEY, JSON.stringify(next));
  return next;
}

function sane(list: unknown): Pair[] {
  if (!Array.isArray(list)) return [];
  return list
    .filter((p): p is Pair =>
      Array.isArray(p) && p.length === 2 &&
      typeof p[0] === 'string' && typeof p[1] === 'string')
    .slice(-MAX_PER_LIST);
}
