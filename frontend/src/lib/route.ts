/**
 * Where you are, spelled as a URL.
 *
 *   /                    the game, against the bot
 *   /rooms               the lobby
 *   /database            every conversation ever recorded. typed, never linked.
 *   /<room>              that room
 *   /<room>/settings     that room, with its settings open
 *
 * The point of the third one is that it can be sent to somebody. A room is a place
 * other people are meant to turn up to, and "open the app, press r, find it in the
 * list" is not an invitation - a link is. Which is also why a link to a room you are
 * not in opens the join form for it rather than an error: the person you sent it to
 * has never been here before, and the only thing missing is their name.
 *
 * Rooms sit at the top level rather than under /rooms/<name> because the link is the
 * feature and the shortest one is the best one. The cost is that room names share a
 * namespace with the app's own paths, so `rooms` is reserved on the server side.
 */

export type Route =
  | { at: 'solo' }
  | { at: 'lobby' }
  | { at: 'database' }
  | { at: 'room'; slug: string; settings: boolean };

export const LOBBY_PATH = 'rooms';
export const DATABASE_PATH = 'database';

export function parse(pathname: string): Route {
  const parts = pathname.split('/').filter(Boolean);
  if (parts.length === 0) return { at: 'solo' };
  if (parts[0] === LOBBY_PATH) return { at: 'lobby' };
  if (parts[0] === DATABASE_PATH) return { at: 'database' };
  return { at: 'room', slug: parts[0], settings: parts[1] === 'settings' };
}

export function path(route: Route): string {
  if (route.at === 'solo') return '/';
  if (route.at === 'lobby') return `/${LOBBY_PATH}`;
  if (route.at === 'database') return `/${DATABASE_PATH}`;
  return `/${route.slug}${route.settings ? '/settings' : ''}`;
}

/** Push a route into the address bar without reloading. */
export function go(route: Route, replace = false) {
  const next = path(route);
  if (next === window.location.pathname) return;
  window.history[replace ? 'replaceState' : 'pushState']({}, '', next);
}

export function current(): Route {
  return parse(window.location.pathname);
}
