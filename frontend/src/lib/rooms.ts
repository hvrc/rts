/**
 * Who you are in a room, and how a room talks to this browser.
 *
 * Identity is a display name and an id this browser made up. There is no account and
 * no password: the id is what makes you the same person after a reload, so the bot can
 * keep calling you by name and the running order doesn't reshuffle every time your
 * wifi blinks. The name is only a label - two people can want the same one, and the
 * server hands the second of them `ana2`.
 *
 * Everything that happens *to* a room arrives on one server-sent event stream rather
 * than as replies to what you sent. That's the whole reason a room needs a different
 * transport from solo play: most of what you see was caused by somebody else.
 */

const USER_KEY = 'rts.user.v1';
const NAME_KEY = 'rts.name.v1';

export interface Member {
  user_id: string;
  name: string;
  present: boolean;
}

export interface RoomState {
  id: string;
  name: string;
  members: Member[];
  count: number;
  bot: boolean;
  timer: boolean;
  reverse: boolean;
  /** Whose go it is, or null when nothing is being enforced. */
  turn: string | null;
  turn_name: string | null;
  /** Wall-clock ms the current turn expires, or null when no clock is running. */
  deadline_ms: number | null;
  chain: string[];
  word: string | null;
  last_active: number;
}

export interface RoomMessage {
  id: string;
  user_id: string | null;
  name: string | null;
  text: string;
  ts: number;
  kind: 'say' | 'bot' | 'system';
  code?: string | null;
  link?: { from: string; to: string } | null;
  /** Why this message didn't count, if it didn't. */
  flag?: 'out_of_turn' | 'rts' | 'duplicate' | null;
}

/** What getting into a room hands back: the room, you in it, and what's been said. */
export interface Entry {
  room: RoomState;
  you: Member;
  messages: RoomMessage[];
}

/** This browser's player id. Generated once and kept - it is the only identity there is. */
export function userId(): string {
  let id = localStorage.getItem(USER_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_KEY, id);
  }
  return id;
}

/** The last name you used, so joining a second room doesn't ask twice. */
export function savedName(): string {
  return localStorage.getItem(NAME_KEY) || '';
}

export function rememberName(name: string) {
  localStorage.setItem(NAME_KEY, name);
}

export class Rooms {
  constructor(private api: string) {}

  private async send(path: string, body?: unknown) {
    const response = await fetch(`${this.api}${path}`, {
      method: body === undefined ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.error || `HTTP ${response.status}`);
    }
    return response.json();
  }

  list(): Promise<{ rooms: RoomState[] }> {
    return this.send('/rooms');
  }

  create(name: string, who: string,
         opts: { bot: boolean; timer: boolean; reverse: boolean }): Promise<Entry> {
    rememberName(who);
    return this.send('/rooms', {
      user_id: userId(), name: who, room_name: name, ...opts,
    });
  }

  join(roomId: string, who: string): Promise<Entry> {
    rememberName(who);
    return this.send(`/rooms/${roomId}/join`, { user_id: userId(), name: who });
  }

  say(roomId: string, message: string) {
    return this.send(`/rooms/${roomId}/say`, { user_id: userId(), message });
  }

  settings(roomId: string, patch: Partial<Pick<RoomState, 'bot' | 'timer' | 'reverse'>>) {
    return this.send(`/rooms/${roomId}/settings`, patch);
  }

  /**
   * Tell the server you're going.
   *
   * `keepalive` because this fires from a page that is on its way out, and an ordinary
   * fetch is cancelled when the document unloads - which would leave you seated in the
   * rotation, holding up a room you had already closed the tab on.
   */
  leave(roomId: string) {
    return fetch(`${this.api}/rooms/${roomId}/leave`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId() }),
      keepalive: true,
    }).catch(() => {});
  }

  /**
   * Watch a room. Returns a function that stops watching.
   *
   * EventSource rather than the hand-rolled reader `/stream` uses: this connection is
   * open for as long as you are in the room, and reconnecting after a dropped network
   * is behaviour worth getting for free rather than writing again.
   */
  watch(
    roomId: string,
    on: {
      message: (m: RoomMessage) => void;
      state: (s: RoomState) => void;
      thinking?: () => void;
    },
  ): () => void {
    const source = new EventSource(`${this.api}/rooms/${roomId}/events`);
    const listen = <T>(name: string, fn?: (data: T) => void) => {
      if (!fn) return;
      source.addEventListener(name, (e) => {
        try {
          fn(JSON.parse((e as MessageEvent).data));
        } catch {
          /* a malformed frame is not worth tearing the room down over */
        }
      });
    };
    listen('message', on.message);
    listen('state', on.state);
    listen('thinking', on.thinking && (() => on.thinking!()));
    return () => source.close();
  }
}
