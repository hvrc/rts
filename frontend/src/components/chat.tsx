import React from 'react';
import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import './chat.css';
import '../skins/aqua.css';
import Header from './Header';
import Rating from './Rating';
import Rooms from './Rooms';
import TurnTimer from './TurnTimer';
import {
  Rooms as RoomsApi,
  userId,
  type Member,
  type RoomMessage,
  type RoomState,
} from '../lib/rooms';
import { current as currentRoute, go, type Route } from '../lib/route';
import { gameId, loadPrefs, ratePair, type Link, type Rating as RatingValue } from '../lib/prefs';
import { applyAccent, isAccentId, sampleWallpaperAccent, DEFAULT_ACCENT, type AccentId } from '../lib/accent';
import {
  DARK_MODE_KEY,
  effectiveDark,
  initialDarkPreference,
  watchSystemDark,
  type DarkModePreference,
} from '../lib/darkMode';

interface Message {
  text: string;
  isUser: boolean;
  showQuestionMark?: boolean;
  link?: Link;          // the leap the bot made (from -> to). only on a played word.
  rating?: RatingValue; // what the human thought of that leap.

  // An empty bot bubble holding the bot's place while it thinks. Renders as the dots.
  pending?: boolean;

  // Set once streamed text starts arriving in that bubble: still pending (the turn
  // isn't settled), but no longer showing dots.
  streaming?: boolean;

  // --- rooms only ---------------------------------------------------------
  /** Who said it. Drawn above the bubble, and only when the speaker changes. */
  who?: string;
  /** The room talking about itself - joins, leaves, settings. Not a bubble. */
  note?: boolean;
  /** Said, but it didn't count: out of turn, or against the rules. */
  void?: boolean;
}

/** A room message as this component wants to draw it. */
function asMessage(m: RoomMessage, me: string): Message {
  return {
    text: m.text,
    isUser: m.user_id === me,
    who: m.kind === 'system' ? undefined : m.name || undefined,
    note: m.kind === 'system',
    void: !!m.flag,
    link: m.link || undefined,
  };
}

interface WordState {
  word: string;
  opacity: number;
  position: {
    x: number;
    y: number;
    rotate: number;
    scale: number;
  };
}

interface ServerResponse {
  response: string;
  train_of_thought: string[][];
  response_code: string;
  link?: Link;
  new_game?: boolean;

  // True when the human is now opening rather than answering: nothing on the board to
  // connect to, so nothing to be timed on.
  opening?: boolean;
}

type Skin = 'aqua' | 'flat';

/**
 * Read one turn off the server-sent event stream.
 *
 * Two event types: `delta` carries more of the reply and is handed to `onDelta` the
 * moment it lands; `done` carries the same payload the old non-streaming endpoint
 * returned, which is what the rest of this component still works from. A turn whose
 * provider cannot stream simply produces no deltas and one `done` - the caller cannot
 * tell the difference except by when the text shows up.
 */
async function readTurn(
  body: ReadableStream<Uint8Array>,
  onDelta: (text: string) => void,
): Promise<ServerResponse | null> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let result: ServerResponse | null = null;

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // Frames are separated by a blank line. A chunk can split one anywhere, so only
    // whole frames are consumed and the remainder stays in the buffer.
    let split = buffer.indexOf('\n\n');
    for (; split !== -1; split = buffer.indexOf('\n\n')) {
      const frame = buffer.slice(0, split);
      buffer = buffer.slice(split + 2);

      let event = 'message';
      let payload = '';
      for (const line of frame.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7).trim();
        else if (line.startsWith('data: ')) payload += line.slice(6);
      }
      if (!payload) continue;

      const parsed = JSON.parse(payload);
      if (event === 'delta') onDelta(parsed as string);
      else if (event === 'done') result = parsed as ServerResponse;
    }
  }

  return result;
}

const SKIN_KEY = 'rts.skin';

/* Versioned on purpose. `rts.accent` was written as "blue" by an earlier build,
   before `wallpaper` was an option - and a stored value beats a new default
   forever, so every existing session stayed blue no matter what the default
   became. Bumping the key retires those values instead of silently honouring a
   choice the user never made. */
const ACCENT_KEY = 'rts.accent.v2';

/* One wallpaper per theme. The `wallpaper` accent samples whichever is showing,
   so flipping the theme moves the accent with it. */
const WALLPAPER_SRC = {
  light: '/wallpaper-light.jpg',
  dark: '/wallpaper-dark.jpg',
} as const;

/** Sampling costs a decode + a canvas read, so each image is only done once. */
const wallpaperAccentCache = new Map<string, string>();

/* Small enough to be useful, large enough that the composer never collapses. */
const MIN_WIDTH = 240;
const MIN_HEIGHT = 220;

/** The eight resize handles: each letter is a side that the drag moves. */
const RESIZE_EDGES = ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'] as const;

/** Milliseconds a character waits before the next one appears. */
const TYPE_MS = 18;

const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/** How long a player has to answer once it is their turn. Both sides get it. */
const TURN_MS = 20_000;

/** Below this the window stops being a window and becomes the whole screen. */
const PHONE = '(max-width: 640px)';

/** `?skin=flat` wins over the stored preference - one URL to compare the two. */
function initialSkin(): Skin {
  const param = new URLSearchParams(window.location.search).get('skin');
  if (param === 'flat' || param === 'aqua') return param;
  return localStorage.getItem(SKIN_KEY) === 'flat' ? 'flat' : 'aqua';
}

function initialAccent(): AccentId {
  const param = new URLSearchParams(window.location.search).get('accent');
  if (isAccentId(param)) return param;
  const saved = localStorage.getItem(ACCENT_KEY);
  if (isAccentId(saved)) return saved;
  localStorage.removeItem('rts.accent'); // retire the pre-v2 value
  return DEFAULT_ACCENT;
}

function Chat() {
  // Backend URL is injected at build time via VITE_API_URL so the backend can move
  // hosts/domains without a code change. Falls back to localhost for dev.
  const API_URL = import.meta.env.VITE_API_URL
    ?? (import.meta.env.PROD
      ? 'https://backend-dot-rts0-462101.ue.r.appspot.com'
      : 'http://localhost:5001');

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [currentTrainOfThought] = useState<string[]>([]);
  const [, setWordPositions] = useState<Array<{x: number, y: number, rotate: number, scale: number}>>([]);
  const [animatingWords, setAnimatingWords] = useState<WordState[]>([]);
  const [isAnimating, setIsAnimating] = useState(false);
  const [serverData, setServerData] = useState<ServerResponse | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [lastProcessedMessage, setLastProcessedMessage] = useState<string | null>(null);

  // Which bot message has been tapped open. Touch has no hover, so the thumbs need a
  // tap to appear; on desktop hover already handles it and this is inert.
  const [tapped, setTapped] = useState<number | null>(null);

  // The three header toggles: r opens the lobby, t is the theme, s flips the letters.
  const [reverse, setReverse] = useState(false);                       // s

  /* Where we are, and the address bar agrees. The route is the source of truth for
     which of the three things this window is showing, rather than a flag per thing:
     with `/`, `/rooms`, `/<room>` and `/<room>/settings` all reachable by link and by
     the back button, a set of booleans alongside them would only be a second opinion
     that could disagree. */
  const [route, setRoute] = useState<Route>(currentRoute);

  const navigate = useCallback((next: Route, replace = false) => {
    go(next, replace);
    setRoute(next);
  }, []);

  // The back button is a real way to move around this app now, so it has to be heard.
  useEffect(() => {
    const pop = () => setRoute(currentRoute());
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);

  /* Kept, and permanently off. The train of thought still renders - the animation
     below is untouched - but nothing turns it on any more: it was the largest field
     the model wrote, generated on every single turn, for something almost nobody
     opened. Deleting it would throw away work that only needs a switch to come back. */
  const [showThoughtProcess] = useState(false);

  /* The room you're in, or null for solo play. `roomMsgs` is kept apart from
     `messages` rather than replacing it so that stepping into a room and back out
     doesn't destroy the game you had going. */
  const [room, setRoom] = useState<RoomState | null>(null);
  const [roomMsgs, setRoomMsgs] = useState<Message[]>([]);
  const [botThinking, setBotThinking] = useState(false);
  const rooms = useMemo(() => new RoomsApi(API_URL), [API_URL]);
  const me = useMemo(() => userId(), []);

  /* Everything about what's on screen, read off the route.
     A URL naming a room you are not in yet is the invitation case: it shows the lobby,
     already asking for the one thing that is missing. */
  const wantedRoom = route.at === 'room' ? route.slug : null;
  const inRoom = !!room && room.id === wantedRoom;
  const lobby = route.at === 'lobby' || (wantedRoom !== null && !inRoom);
  const joiningSlug = wantedRoom !== null && !inRoom ? wantedRoom : null;
  const roomBarOpen = route.at === 'room' && route.settings && inRoom;

  // Dark mode is a tri-state preference (`t`), resolved to a boolean for the DOM.
  const [darkPref, setDarkPref] = useState<DarkModePreference>(initialDarkPreference);
  const [isDark, setIsDark] = useState(() => effectiveDark(initialDarkPreference()));

  // Appearance: the skin (shape + gloss) and the accent (hue). Separate axes
  // from the theme, revealed by holding `t`.
  const [skin, setSkin] = useState<Skin>(initialSkin);
  const [accent, setAccent] = useState<AccentId>(initialAccent);
  const [wallpaperAccent, setWallpaperAccent] = useState<string | null>(null);
  const [appearanceOpen, setAppearanceOpen] = useState(false);

  /* Wall-clock ms when this turn expires, or null when no clock is running - while
     the bot is thinking, during the intro, and once a game has been lost. */
  const [deadline, setDeadline] = useState<number | null>(null);
  const startClock = useCallback(() => setDeadline(Date.now() + TURN_MS), []);
  const stopClock = useCallback(() => setDeadline(null), []);

  /* Both sides are on the clock, so expiry needs to know whose it was. A ref rather
     than state: the expiry callback is held by an animation frame and would otherwise
     close over whichever turn it was created in. */
  const turnRef = useRef<'human' | 'bot'>('human');
  const inFlight = useRef<AbortController | null>(null);

  /* Same reason as turnRef: the expiry callback is held by an animation frame, so it
     has to be able to see whether there's a room *now* rather than when it was made. */
  const roomRef = useRef<RoomState | null>(null);

  const latestBotMessageRef = useRef<HTMLDivElement>(null);
  const chatBoxRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const windowRef = useRef<HTMLDivElement>(null);

  // Where the window has been dragged to. `null` means "still centered" - the
  // CSS handles that case, and we only start writing left/top once the user has
  // actually moved it, so resizing the viewport keeps re-centering until then.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const [dragging, setDragging] = useState(false);

  // On a phone the widget stops being a draggable window and becomes the app: full
  // bleed, no drag, no resize. The glass is translucent, so the wallpaper still reads
  // through it rather than being lost.
  const [phone, setPhone] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(PHONE).matches);

  useEffect(() => {
    const query = window.matchMedia(PHONE);
    const sync = (e: MediaQueryListEvent) => setPhone(e.matches);
    query.addEventListener('change', sync);
    return () => query.removeEventListener('change', sync);
  }, []);

  // Explicit size, once resized. `null` keeps the CSS defaults (280 wide, up to
  // 480 tall) so the window still adapts to short viewports until it's touched.
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [resizing, setResizing] = useState(false);

  const startDrag = useCallback((e: React.PointerEvent) => {
    // The traffic lights and the appearance strip are controls, not handle.
    if ((e.target as HTMLElement).closest('button')) return;
    const el = windowRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const grabX = e.clientX - rect.left;
    const grabY = e.clientY - rect.top;
    setDragging(true);

    const move = (ev: PointerEvent) => {
      // Keep at least a corner of the window on screen, so it can never be
      // thrown somewhere it can't be grabbed back from.
      const maxX = window.innerWidth - 60;
      const maxY = window.innerHeight - 40;
      setPos({
        x: Math.min(Math.max(ev.clientX - grabX, 60 - rect.width), maxX),
        y: Math.min(Math.max(ev.clientY - grabY, 0), maxY),
      });
    };

    const end = () => {
      setDragging(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
    };

    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
  }, []);

  /**
   * Resize from any edge or corner. `edge` is a compass string ('n', 'se', ...);
   * each letter names a side that moves, which keeps one handler for all eight
   * instead of eight near-identical ones.
   *
   * Dragging a west or north edge moves the window as well as resizing it, so
   * position and size are always set together - and the position is pinned on
   * pointerdown, because the CSS centering would otherwise keep re-centering the
   * window as it grew and the opposite edge would crawl away from the pointer.
   */
  const startResize = useCallback((edge: string) => (e: React.PointerEvent) => {
    e.stopPropagation(); // don't also start a window drag
    const el = windowRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    const startX = e.clientX;
    const startY = e.clientY;
    const from = { x: rect.left, y: rect.top, w: rect.width, h: rect.height };

    setPos({ x: from.x, y: from.y });
    setSize({ w: from.w, h: from.h });
    setResizing(true);

    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;
      let { x, y, w, h } = from;

      if (edge.includes('e')) w = from.w + dx;
      if (edge.includes('s')) h = from.h + dy;
      if (edge.includes('w')) w = from.w - dx;
      if (edge.includes('n')) h = from.h - dy;

      w = Math.min(Math.max(w, MIN_WIDTH), window.innerWidth);
      h = Math.min(Math.max(h, MIN_HEIGHT), window.innerHeight);

      // Anchor the edge that isn't being dragged. Deriving x from the clamped
      // width (rather than from dx) is what stops the far side sliding once the
      // minimum is hit.
      if (edge.includes('w')) x = from.x + from.w - w;
      if (edge.includes('n')) y = from.y + from.h - h;

      setSize({ w, h });
      setPos({ x, y });
    };

    const end = () => {
      setResizing(false);
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', end);
      window.removeEventListener('pointercancel', end);
    };

    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', end);
    window.addEventListener('pointercancel', end);
  }, []);

  // `reverse` is read inside async handlers that would otherwise close over a stale
  // value; the ref always has the current one.
  const reverseRef = useRef(reverse);
  useEffect(() => { reverseRef.current = reverse; }, [reverse]);
  useEffect(() => { roomRef.current = room; }, [room]);

  // Theme lives on <html> so index.css can drive every color from one attribute.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    document.documentElement.style.colorScheme = isDark ? 'dark' : 'light';
  }, [isDark]);

  // Preference -> resolved boolean, and persist the preference (not the result,
  // so "system" stays "system" across reloads instead of freezing whatever the
  // OS happened to be at the time).
  useEffect(() => {
    localStorage.setItem(DARK_MODE_KEY, darkPref);
    setIsDark(effectiveDark(darkPref));
  }, [darkPref]);

  // Follow the OS while the preference is `system`; an explicit override wins.
  useEffect(() => {
    if (darkPref !== 'system') return;
    return watchSystemDark(setIsDark);
  }, [darkPref]);

  // Sample the accent out of whichever wallpaper is showing. Re-runs on theme
  // change, since the two images are different colors; cached so the second
  // visit to a theme is instant. Until the first sample resolves, the
  // `wallpaper` accent falls back to blue and its swatch shows a rainbow.
  useEffect(() => {
    const src = isDark ? WALLPAPER_SRC.dark : WALLPAPER_SRC.light;
    const cached = wallpaperAccentCache.get(src);
    if (cached) {
      setWallpaperAccent(cached);
      return;
    }
    let alive = true;
    sampleWallpaperAccent(src).then((hex) => {
      if (!hex) return;
      wallpaperAccentCache.set(src, hex);
      if (alive) setWallpaperAccent(hex);
    });
    return () => { alive = false; };
  }, [isDark]);

  // Same mechanism, second axis: the skin selects which stylesheet's rules win.
  useEffect(() => {
    document.documentElement.setAttribute('data-skin', skin);
    localStorage.setItem(SKIN_KEY, skin);
  }, [skin]);

  // The accent is derived, not stored as a palette - one hex in, a handful of
  // vars out. It depends on the theme because the same accent needs different
  // math on a light window than on a dark one.
  useEffect(() => {
    applyAccent(accent, isDark, wallpaperAccent);
    localStorage.setItem(ACCENT_KEY, accent);
  }, [accent, isDark, wallpaperAccent]);

  /**
   * Measure the floating bars so the conversation can be padded clear of them.
   *
   * Neither bar is a fixed height - the top one grows when a panel opens under it, and
   * the lobby has no composer at all - so both are measured rather than assumed.
   *
   * The two are handled independently on purpose. Requiring both to exist before
   * measuring either meant that opening the lobby, which removes the composer, took
   * the observer down with it: `--chrome-top` then froze at whatever it last read,
   * and if a panel happened to be open at the time the lobby kept a panel's worth of
   * empty space above its first line for the rest of the session.
   */
  useEffect(() => {
    const win = windowRef.current;
    if (!win) return;

    const sync = () => {
      const header = win.querySelector<HTMLElement>('.rts-header-group');
      const composer = win.querySelector<HTMLElement>('.rts-composer');
      win.style.setProperty('--chrome-top', `${header?.offsetHeight ?? 0}px`);
      win.style.setProperty('--chrome-bottom', `${composer?.offsetHeight ?? 0}px`);
    };
    sync();

    const observer = new ResizeObserver(sync);
    for (const selector of ['.rts-header-group', '.rts-composer']) {
      const el = win.querySelector(selector);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
    // The observer catches a bar changing size; these catch one appearing or being
    // taken away, which it cannot see because there is nothing left to watch.
  }, [lobby, appearanceOpen, roomBarOpen]);

  /**
   * Track the visual viewport, which is what the keyboard actually changes.
   *
   * Opening the keyboard shrinks the *visual* viewport but leaves the *layout* viewport
   * alone, and `position: fixed` is anchored to the layout one. So the window kept its
   * full height, the keyboard covered the bottom of it, and Safari scrolled the whole
   * thing up to reveal the input - taking the conversation off the top of the screen
   * and leaving the cut-off tail.
   *
   * Publishing the visual viewport's height and offset as variables lets the window
   * size itself to the space actually visible, which is what a chat app does: the
   * composer sits on the keyboard, the messages keep the rest, and nothing scrolls off.
   */
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;

    const root = document.documentElement;
    const sync = () => {
      root.style.setProperty('--viewport-height', `${viewport.height}px`);
      root.style.setProperty('--viewport-offset', `${viewport.offsetTop}px`);
    };
    sync();

    // `resize` fires when the keyboard opens or closes; `scroll` fires as iOS settles
    // the offset afterwards, and without it the window lands a few pixels adrift.
    viewport.addEventListener('resize', sync);
    viewport.addEventListener('scroll', sync);
    return () => {
      viewport.removeEventListener('resize', sync);
      viewport.removeEventListener('scroll', sync);
    };
  }, []);

  /**
   * Scroll the conversation to the end.
   *
   * Deliberately `scrollTop = scrollHeight` rather than scrolling the end marker into
   * view. The composer is an absolute overlay, so the scroll container's box runs on
   * underneath it - which means the browser considers the last bubble "in view" while
   * it is sitting behind the input, and `scrollIntoView` stops there satisfied. Asking
   * for the maximum instead lands past the container's bottom padding, and that padding
   * is exactly the height of the bar in the way.
   *
   * Instant, not smooth, and that is load-bearing rather than a taste call. A smooth
   * scroll fires `scroll` events all the way down, and every one of them is read below
   * as "the view is nowhere near the bottom" - so the animation un-pins itself on its
   * own way there, and the *next* message doesn't scroll at all. Setting scrollTop
   * lands in one step, and the single event it fires is the one at the bottom.
   */
  const scrollToBottom = useCallback(() => {
    const el = messagesContainerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, []);

  /* Whether the view is following the conversation.
     Solo, every message answers something you just did, so you are always at the
     bottom when one arrives and this is always true. In a room they arrive while you
     are reading something further up - and dragging the view back mid-sentence every
     time somebody else types is worse than missing the newest line. So the scroll only
     follows when it was already following, and going back to the bottom re-arms it. */
  const pinned = useRef(true);
  const STICK_PX = 80;

  const onScroll = useCallback(() => {
    const el = messagesContainerRef.current;
    // The lobby borrows this same scroll container, and it opens by jumping to the top
    // of the room list. That is not you walking away from the conversation, so it must
    // not be read as such - otherwise picking a room arrives with the view unpinned.
    if (!el || lobby) return;
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < STICK_PX;
  }, [lobby]);

  useEffect(() => {
    // The lobby is the one thing in this pane that reads downwards: "new room" is the
    // first line and the rest is a list under it, so anchoring it to the bottom would
    // open it showing the least interesting room.
    if (lobby) {
      messagesContainerRef.current?.scrollTo({ top: 0, behavior: 'auto' });
      return;
    }
    if (pinned.current) scrollToBottom();
    // `botThinking` is in here because the placeholder bubble changes the height of
    // the conversation without changing any message in it.
  }, [messages, roomMsgs, botThinking, lobby, scrollToBottom]);

  /* Walking into a room replaces the whole conversation, so there is nothing to
     animate towards and no earlier position worth keeping. */
  useEffect(() => {
    pinned.current = true;
    scrollToBottom();
  }, [room?.id, scrollToBottom]);

  /* Keep the newest message in view as the keyboard takes its space, the way every
     chat app does - otherwise the conversation stays where it was and the last thing
     said ends up behind the keyboard. */
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const stick = () => scrollToBottom();
    viewport.addEventListener('resize', stick);
    return () => viewport.removeEventListener('resize', stick);
  }, [scrollToBottom]);

  // Flipping the rule does not restart the game - the chain survives, and the new rule
  // governs every word from here on. The bot just says so.
  // The AI calls the flip, and spells out what actually changed. Announce outside the
  // state updater - StrictMode invokes updaters twice, which would post the line twice.
  const toggleReverse = useCallback(async () => {
    const next = !reverse;
    setReverse(next);

    // In a room the rule belongs to the room, not to you - so it goes to the server,
    // which announces it to everybody. Flipping it locally would leave the person who
    // pressed it playing a different game from everyone else.
    if (room) {
      rooms.settings(room.id, { reverse: next }).catch(() => setReverse(reverse));
      return;
    }

    setMessages(m => [...m, { text: '', isUser: false }]);
    await announce(
      next
        ? "new rules... every word has to start with r t or s now, no other letters allowed"
        : "new rules... back to normal. no word can start with r, t or s"
    );
  }, [reverse, room, rooms]);

  /**
   * `r`. The window turns round: the chat becomes the lobby, and back.
   *
   * From inside a room it steps out to the lobby rather than straight to solo play,
   * because the reason to leave a room is nearly always to go to a different one.
   */
  const toggleRooms = useCallback(() => {
    if (room) {
      rooms.leave(room.id);
      setRoom(null);
      setRoomMsgs([]);
      navigate({ at: 'lobby' });
      return;
    }
    navigate(lobby ? { at: 'solo' } : { at: 'lobby' });
  }, [lobby, navigate, room, rooms]);

  /* Room settings live behind a hold on `r`, the same way appearance lives behind a
     hold on `t`. They belong to the room rather than to you, so changing one is
     announced to everybody - which is also why they aren't in a menu only you can see. */
  const setRoomSetting = useCallback((patch: { bot?: boolean; timer?: boolean }) => {
    if (room) rooms.settings(room.id, patch).catch(() => {});
  }, [room, rooms]);

  /* The lobby backed out of a join form, so the URL should stop naming a room we are
     not in. Replaces rather than pushes: the join form and the list it came from are
     one stop, not two, and pushing would make `back` bounce between them. */
  const browse = useCallback(() => {
    if (route.at !== 'lobby') navigate({ at: 'lobby' }, true);
  }, [navigate, route.at]);

  /** Somebody got into a room. Everything from here arrives on its event stream. */
  const enterRoom = useCallback((state: RoomState, log: RoomMessage[], _you: Member) => {
    setRoom(state);
    setRoomMsgs(log.map(m => asMessage(m, me)));
    setReverse(state.reverse);
    // `replace` when the URL already names this room: arriving on a link and then
    // pushing the same path would make the back button a no-op that looks broken.
    navigate({ at: 'room', slug: state.id, settings: false },
             route.at === 'room' && route.slug === state.id);
  }, [me, navigate, route]);

  // Rating is on the link, not the word: "war" alone teaches the bot nothing, but
  // "from peace it leapt to war, and I liked that" is a taste it can act on. Saved to
  // localStorage and sent with every subsequent turn.
  const rate = useCallback((index: number, link: Link, rating: RatingValue) => {
    ratePair(link, rating);
    setMessages(m => m.map((msg, i) => (i === index ? { ...msg, rating } : msg)));
  }, []);

  // Clicking `t` is the quick flip: it always lands on an explicit light/dark,
  // never back on `system`. Choosing `system` is a deliberate act, done from the
  // appearance strip - it shouldn't be something you cycle into by accident.
  const toggleTheme = useCallback(() => {
    setDarkPref(effectiveDark(darkPref) ? 'light' : 'dark');
  }, [darkPref]);

  /**
   * Stay subscribed to the room for as long as you're in it.
   *
   * Everything the room does arrives here - other people's messages, the bot's turn,
   * the clock changing hands - because none of it was caused by anything this browser
   * asked for. Your own messages come back the same way rather than being echoed
   * locally, so there is exactly one thing deciding what the room looks like.
   */
  useEffect(() => {
    if (!room) return;
    const id = room.id;

    const stop = rooms.watch(id, {
      message: (m) => {
        setBotThinking(false);
        setRoomMsgs(prev => [...prev, asMessage(m, me)]);
      },
      state: (s) => {
        setRoom(s);
        setReverse(s.reverse);
        // The room owns the clock, including the expiry: with round-robin the current
        // player can have closed their laptop, and a countdown owned by their browser
        // would then never fire. This just draws what the server says.
        setDeadline(s.deadline_ms);
      },
      thinking: () => setBotThinking(true),
    });

    // A closing tab has to say so, or it stays seated in the rotation and every lap
    // stalls for twenty seconds on somebody who has gone.
    const bye = () => rooms.leave(id);
    window.addEventListener('pagehide', bye);

    return () => {
      window.removeEventListener('pagehide', bye);
      stop();
    };
  }, [room?.id, rooms, me]);   // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Swap the waiting bubble for the real reply. The placeholder is the one message in
   * flight, so land on it rather than appending - otherwise the dots would linger above
   * the answer.
   */
  /**
   * Show `text` in the waiting bubble.
   *
   * The placeholder keeps its `pending` flag so `settlePending` can still find it when
   * the turn finishes, but it stops rendering the thinking dots as soon as there is a
   * character to show - the dots and the answer would otherwise share the bubble.
   */
  const setPendingText = useCallback((text: string) => {
    setMessages(prev => {
      const next = [...prev];
      const at = next.map(m => !!m.pending).lastIndexOf(true);
      if (at === -1) return prev;
      next[at] = { ...next[at], text, streaming: true };
      return next;
    });
  }, []);

  const settlePending = useCallback((botMessage: Message, flagUnrelated = false) => {
    setMessages(prev => {
      const next = [...prev];
      const at = next.map(m => !!m.pending).lastIndexOf(true);
      if (at === -1) {
        next.push(botMessage);       // no placeholder (shouldn't happen) - don't lose the reply
        return next;
      }
      next[at] = botMessage;
      if (flagUnrelated) {
        for (let i = at - 1; i >= 0; i--) {
          if (next[i].isUser) {
            next[i] = { ...next[i], showQuestionMark: true };
            break;
          }
        }
      }
      return next;
    });
  }, []);

  /**
   * The clock ran out. Tell the server, not a faked message.
   *
   * /timeout is its own route: running out of time is something this client observed,
   * not something the player typed, and posting an invented sentence to /echo would
   * write words they never said into the transcript and into the model's memory of the
   * conversation.
   */
  const handleExpire = useCallback(async () => {
    // In a room the clock is the server's. It is already counting the same twenty
    // seconds and will announce the skip to everyone at once; a client that also
    // reported the expiry would be racing the four other browsers doing the same.
    if (roomRef.current) return;

    stopClock();
    const loser = turnRef.current;
    // A forfeit can leave either side to open; the server says which.
    let opensNext = false;

    if (loser === 'bot') {
      // Abandon the turn it failed to finish. Without this the answer could still
      // arrive seconds later and land in a game that has already been restarted,
      // playing a word into a chain it was never connected to.
      inFlight.current?.abort();
      inFlight.current = null;
    } else {
      setMessages(prev => [...prev, { text: '', isUser: false, pending: true }]);
    }

    try {
      const response = await fetch(`${API_URL}/timeout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          game_id: gameId(),
          reverse: reverseRef.current,
          who: loser,
        }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data: ServerResponse = await response.json();
      settlePending({ text: data.response, isUser: false });
      opensNext = !!data.opening;
    } catch (error) {
      console.error('Timeout:', error);
      settlePending({
        text: loser === 'bot'
          ? "ran out of time there. that one's yours - new game, you start"
          : "time's up, that one's yours. new game?",
        isUser: false,
      });
    }
    // A fresh game has opened and the next move is theirs either way - but if the bot
    // handed the opening back rather than playing into it, they have nothing to answer
    // and the clock stays down.
    turnRef.current = 'human';
    if (!opensNext) startClock();
  }, [API_URL, settlePending, startClock, stopClock]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    /* In a room, sending is all this does. The message comes back over the event
       stream like everyone else's, and the answer - if there is one - may well arrive
       after somebody else has already spoken. Echoing it locally as well would put it
       on screen twice and make this browser's copy of the room the one that disagrees
       with the other four. */
    if (room) {
      const text = inputText;
      setInputText('');
      try {
        await rooms.say(room.id, text);
      } catch {
        setInputText(text);      // hand it back rather than swallowing what they typed
      }
      return;
    }

    // The bot starts "thinking" the instant you hit send, in every mode - not only when
    // the train of thought is on.
    setMessages(prev => [
      ...prev,
      { text: inputText, isUser: true },
      { text: '', isUser: false, pending: true },
    ]);
    const userInput = inputText;
    setInputText('');
    let settled: ServerResponse | null = null;
    // The clock does not stop, it changes hands: the bot is on it now.
    turnRef.current = 'bot';
    startClock();

    try {
      const controller = new AbortController();
      inFlight.current = controller;

      const response = await fetch(`${API_URL}/stream`, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userInput,
          game_id: gameId(),
          reverse: reverseRef.current,
          preferences: loadPrefs(),   // taste travels with every turn
          // The train of thought is the largest thing the model writes and it is only
          // ever drawn when `s` is on. Asking for it regardless was roughly tripling
          // the turn to generate an animation nobody would see.
          thoughts: showThoughtProcess,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      /* The reply types itself out, but against a buffer the stream is still filling
         rather than against a finished string.

         The old typewriter ran after the whole response had arrived, so its cost was
         added to the wait: fifty milliseconds a character on top of an answer that
         already existed. This one starts as soon as the first characters land and
         stops when it catches up, so on a one-word reply it is a brief flourish and on
         a long one it is revealing text that is still being written anyway. */
      const buffered = { text: '', complete: false };

      const typing = (async () => {
        let shown = 0;
        for (;;) {
          if (shown < buffered.text.length) {
            shown += 1;
            setPendingText(buffered.text.slice(0, shown));
            await wait(TYPE_MS);
          } else if (buffered.complete) {
            return;
          } else {
            await wait(16);        // caught up; idle until more arrives
          }
        }
      })();

      const data = await readTurn(response.body, (text) => { buffered.text += text; });
      buffered.complete = true;
      await typing;

      if (!data) throw new Error('stream ended without a result');
      settled = data;

      // `link` is present only when the bot actually played a word, which is exactly
      // when there is something worth rating. `new_game` is deliberately not surfaced:
      // the backend wipes the board, the bot says so in its own words, and the
      // conversation just carries on.
      const botMessage: Message = {
        text: data.response,
        isUser: false,
        link: data.link,
      };

      settlePending(botMessage, data.response_code === 'UNRELATED');
      setLastProcessedMessage(userInput);

      if (showThoughtProcess && data.train_of_thought && data.train_of_thought.length > 0 && userInput !== lastProcessedMessage) {
        setServerData(data);
        setIsTyping(true);
      }

    } catch (error) {
      // An abort means the bot ran out its own clock and handleExpire has already
      // settled the bubble with the forfeit - reporting "?" over the top would
      // replace that with an error the player never hit.
      if ((error as Error)?.name !== 'AbortError') {
        console.error('Error:', error);
        // Settle, don't append - otherwise the dots spin forever above the "?".
        settlePending({ text: "?", isUser: false });
      }
    } finally {
      // Back to them - including after an error, or the game would sit dead
      // with no clock and no way to notice.
      turnRef.current = 'human';
      // An opening move is not a response, so it is not timed. Anything else is.
      if (settled?.opening) stopClock(); else startClock();
      inFlight.current = null;
    }
  };

  useEffect(() => {
    let mounted = true;

    const initializeChat = async () => {
      if (!mounted) return;

      await fetch(`${API_URL}/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId(), reverse: reverseRef.current }),
      });

      const welcomeMessages = [
        'we say words back n forth',
        'they have to be kinda related',
        "they can't start with r t or s",
        'u start...',
      ];

      // The intro keeps its typewriter. Nothing is waiting on it - the player has just
      // arrived and there is no turn in flight - so the delay here buys the opening its
      // pacing rather than costing anyone a reply. It types into the message itself now
      // instead of through shared animation state, which the streamed replies retired.
      for (const message of welcomeMessages) {
        if (!mounted) break;

        setMessages(prev => [...prev, { text: "", isUser: false }]);

        for (let i = 0; i < message.length; i++) {
          if (!mounted) break;
          await new Promise(resolve => setTimeout(resolve, 25));
          setMessages(prev => {
            const next = [...prev];
            next[next.length - 1] = { ...next[next.length - 1], text: message.slice(0, i + 1) };
            return next;
          });
        }

        await new Promise(resolve => setTimeout(resolve, 100));
      }

      // No clock here. The intro ends on "u start...", which is an opening move -
      // there is no word on the board yet, so there is nothing to answer and
      // nothing to be slow about.
    };

    initializeChat();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (currentTrainOfThought.length > 0) {
      const newPositions = currentTrainOfThought.map(() => ({
        x: Math.random() * 260 - 35,
        y: Math.random() * 430,
        rotate: Math.random() * 30 - 15,
        scale: 0.8 + Math.random() * 0.4
      }));
      setWordPositions(newPositions);
    }
  }, [currentTrainOfThought]);

  useEffect(() => {
    if (!showThoughtProcess || !serverData?.train_of_thought || !Array.isArray(serverData.train_of_thought)) {
      setIsAnimating(false);
      setIsTyping(false);
      setAnimatingWords([]);
      return;
    }

    const animate = async () => {
      setIsAnimating(true);
      setIsTyping(true);

      for (let i = 0; i < serverData.train_of_thought.length - 1; i++) {
        const currentList = serverData.train_of_thought[i];
        const nextList = serverData.train_of_thought[i + 1];

        if (i === 0) {
          const positions = new Map(
            currentList.map(word => [word, {
              x: Math.random() * 260 - 35,
              y: Math.random() * 430,
              rotate: Math.random() * 30 - 15,
              scale: 0.9 + Math.random() * 0.2
            }])
          );

          setAnimatingWords(
            currentList.map(word => ({
              word,
              opacity: 0,
              position: positions.get(word) || { x: 0, y: 0, rotate: 0, scale: 1 }
            }))
          );

          await new Promise(resolve => setTimeout(resolve, 50));

          for (let j = 0; j < currentList.length; j++) {
            setAnimatingWords(prev =>
              prev.map((w, index) =>
                index === j ? { ...w, opacity: 1 } : w
              )
            );
            await new Promise(resolve => setTimeout(resolve, 50));
          }

          await new Promise(resolve => setTimeout(resolve, 100));
        }

        const wordsToRemove = currentList.filter(word => !nextList.includes(word));

        if (wordsToRemove.length > 0) {
          for (const word of wordsToRemove) {
            setAnimatingWords(prev =>
              prev.map(w => ({
                ...w,
                opacity: w.word === word ? 0 : w.opacity
              }))
            );
            await new Promise(resolve => setTimeout(resolve, 100));
          }
        }

        if (i === serverData.train_of_thought.length - 2) {
          await new Promise(resolve => setTimeout(resolve, 500));
          setIsTyping(false);

          await announce(messages[messages.length - 1].text);

          await new Promise(resolve => setTimeout(resolve, 300));
          setAnimatingWords(prev =>
            prev.map(w => ({
              ...w,
              opacity: 0
            }))
          );
        }
      }
    };

    animate();

    return () => {
      setAnimatingWords([]);
      setIsAnimating(false);
      setIsTyping(false);
    };
  }, [serverData?.train_of_thought, showThoughtProcess]);

  /**
   * Put a locally-authored line into the empty bubble that was just pushed for it.
   *
   * This used to type the text out one character at a time. That made sense when every
   * reply arrived complete and instantly - the typewriter was the only thing making a
   * turn feel progressive. Now the bot's own replies stream from the server as they are
   * written, so a per-character delay here is no longer a reveal, only a wait: at 25ms a
   * character it was adding a second to a forty-character line that already existed in
   * full. The two lines it still serves are the rule-flip announcement and the reset
   * message, neither of which the player is waiting on.
   */
  const announce = async (text: string) => {
    if (!text) return;
    for (let i = 1; i <= text.length; i++) {
      setMessages(prev => {
        const next = [...prev];
        if (!next.length) return prev;
        next[next.length - 1] = { ...next[next.length - 1], text: text.slice(0, i) };
        return next;
      });
      await wait(TYPE_MS);
    }
  };

  /* What's on screen: the room's messages, or the solo game's. In a room the bot gets
     a placeholder bubble while it's thinking, exactly as it does solo - it just comes
     from the room telling everyone at once rather than from this browser knowing it
     asked. */
  const shown = inRoom
    ? (botThinking ? [...roomMsgs, { text: '', isUser: false, pending: true }] : roomMsgs)
    : messages;

  return (
    <div
      ref={windowRef}
      className={`rts-window${dragging ? ' is-dragging' : ''}${resizing ? ' is-resizing' : ''}${phone ? ' is-phone' : ''}`}
      style={{
        position: 'fixed',
        display: 'flex',
        flexDirection: 'column',
        ...(phone
          // The screen, minus whatever the keyboard has taken. Falls back to dvh on a
          // browser without visualViewport, which is the pre-keyboard behaviour rather
          // than a broken one.
          ? {
              left: 0,
              top: 'var(--viewport-offset, 0px)',
              width: '100%',
              height: 'var(--viewport-height, 100dvh)',
            }
          // Untouched: 280 wide and as tall as fits, capped at 480. Once resized,
          // both become explicit and the cap no longer applies.
          : {
              width: size ? size.w : 280,
              height: size ? size.h : '100%',
              ...(size ? null : { maxHeight: 480 }),
              // Once dragged, explicit coordinates replace the CSS centering.
              ...(pos ? { left: pos.x, top: pos.y, transform: 'none' } : null),
            }),
      }}
    >
      {/* No resize handles on a phone: the window is the screen, and 7px grab strips
          along the edges would only intercept scrolls. */}
      {!phone && RESIZE_EDGES.map((edge) => (
        <div
          key={edge}
          className={`rts-resize rts-resize--${edge}`}
          onPointerDown={startResize(edge)}
        />
      ))}
      <Header
        rooms={{ on: lobby || inRoom, toggle: toggleRooms }}
        theme={{ on: isDark, toggle: toggleTheme }}
        reverse={{ on: reverse, toggle: toggleReverse }}
        appearance={{
          open: appearanceOpen,
          toggleOpen: () => setAppearanceOpen((o) => !o),
          skin,
          setSkin,
          accent,
          setAccent,
          wallpaperAccent,
          darkPref,
          setDarkPref,
        }}
        // the traffic lights where a touch is far more likely to be a scroll.
        onDragStart={phone ? () => {} : startDrag}
        // Whose go it is, next to the clock that's counting it down. Only in a room:
        // solo, the clock alone says it, because there are only two of you.
        turn={room?.turn_name ? (
          <div className={`rts-turn${room.turn === me ? ' is-you' : ''}`}>
            {room.turn === me ? 'your go' : room.turn_name}
          </div>
        ) : undefined}
        clock={<TurnTimer deadline={deadline} duration={TURN_MS}
                          onExpire={handleExpire} />}
        onHoldRooms={inRoom && room
          ? () => navigate({ at: 'room', slug: room.id, settings: !roomBarOpen })
          : undefined}
        roomBar={room && roomBarOpen ? (
          <div className="rts-appearance rts-roombar">
            <div className="rts-roombar-name">
              {room.name}
              <span className="rts-roombar-who">
                {room.members.map(m => m.name).join(', ')}
              </span>
            </div>
            <div className="rts-skins">
              <button type="button" aria-pressed={room.bot}
                      className={`rts-skin${room.bot ? ' is-on' : ''}`}
                      onClick={() => setRoomSetting({ bot: !room.bot })}>
                bot
              </button>
              <button type="button" aria-pressed={room.timer}
                      className={`rts-skin${room.timer ? ' is-on' : ''}`}
                      onClick={() => setRoomSetting({ timer: !room.timer })}>
                clock
              </button>
            </div>
          </div>
        ) : undefined}
      />
      <div
        ref={chatBoxRef}
        style={{
          flex: 1,
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative',
          overflow: 'hidden'
        }}
      >
        <div
          ref={messagesContainerRef}
          className="messages-container"
          onScroll={onScroll}
          style={{
            flex: 1,
            overflowY: 'scroll',
            WebkitOverflowScrolling: 'touch',
            msOverflowStyle: 'none',
            scrollbarWidth: 'none'
          }}
        >
          {isAnimating && showThoughtProcess && (
            <div className="train-of-thought" style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%',
              pointerEvents: 'none',
              zIndex: 10,
              padding: '10px'
            }}>
              {animatingWords.map((wordState, index) => (
                <div
                  key={`${wordState.word}-${index}`}
                  style={{
                    position: 'absolute',
                    padding: '2px 4px',
                    fontSize: '12px',
                    color: 'var(--tot-text)',
                    whiteSpace: 'nowrap',
                    transform: `translate(${
                      Math.min(Math.max(wordState.position.x, 0), 260)
                    }px, ${
                      Math.min(Math.max(wordState.position.y, 0), 430)
                    }px) rotate(${wordState.position.rotate}deg) scale(${wordState.position.scale})`,
                    opacity: wordState.opacity,
                    transition: `opacity ${
                      wordState.opacity === 0 ? '2s' :
                      wordState.opacity === 1 ? '1s' :
                      '0.1s'
                    } ${
                      wordState.opacity === 0 ? 'ease-out' : 'ease-in'
                    }`
                  }}
                >
                  {wordState.word}
                </div>
              ))}
            </div>
          )}
          {lobby ? (
            <Rooms
              api={rooms}
              onEnter={enterRoom}
              reverse={reverse}
              joining={joiningSlug}
              onBrowse={browse}
            />
          ) : shown.map((message, index) => {
            // The room talking about itself. A caption, not a bubble - nobody said it.
            if (message.note) {
              return <div key={index} className="rts-note">{message.text}</div>;
            }

            /* The name goes above the bubble only when the speaker changes, so a run
               of messages from one person reads as one person talking rather than as a
               column of labels. Your own messages never get one: they're on your side
               of the window, which already says who sent them. */
            const previous = shown[index - 1];
            const heading = message.who && !message.isUser
              && !(previous && previous.who === message.who && !previous.note)
              ? message.who : null;

            return (
              <div
                key={index}
                // `is-tapped` is what reveals the thumbs on touch, where there is no hover.
                className={`rts-msg ${message.isUser ? 'is-user' : 'is-bot'}${tapped === index ? ' is-tapped' : ''}`}
                onClick={message.link ? () => setTapped(t => (t === index ? null : index)) : undefined}
                ref={!message.isUser && index === shown.length - 1 ? latestBotMessageRef : null}
              >
                <div className="rts-msg-body">
                  {heading && <div className="rts-who">{heading}</div>}
                  {message.isUser && message.showQuestionMark && (
                    <div className="question-mark-circle">
                      ?
                    </div>
                  )}
                  <div className={`rts-bubble${message.isUser ? ' is-user' : ''}${message.void ? ' is-void' : ''}`}>
                    {/* Dots while the request is in flight and while the train of thought
                        is still narrowing down - but not once streamed text has started
                        landing in this bubble, which replaces them. */}
                    {(message.pending && !message.streaming)
                     || (!message.isUser && index === shown.length - 1
                         && isTyping && showThoughtProcess) ? (
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    ) : (
                      message.text
                    )}
                  </div>
                  {/* inside the relative wrapper: the circles pin to the bubble's corners,
                      same as the "?" badge above */}
                  {message.link && !inRoom && (
                    <Rating
                      value={message.rating}
                      onRate={(r) => rate(index, message.link!, r)}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
        {/* No composer over the lobby: there is nothing to say to a list of rooms, and
            it asks for what it needs in its own fields. */}
        {!lobby && (
          <form className="rts-composer" onSubmit={handleSubmit}>
            <input
              className="rts-input"
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder=""
            />
            <button className="rts-send" type="submit" aria-label="send" />
          </form>
        )}
      </div>
    </div>
  );
}

export default Chat;
