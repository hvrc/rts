import React from 'react';
import { useState, useRef, useEffect, useCallback } from 'react';
import './chat.css';
import '../skins/aqua.css';
import Header from './Header';
import Rating from './Rating';
import TurnTimer from './TurnTimer';
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

  // The three header toggles.
  const [showThoughtProcess, setShowThoughtProcess] = useState(false); // s
  const [reverse, setReverse] = useState(false);                       // r

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

  const messagesEndRef = useRef<HTMLDivElement>(null);
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
   * The top bar is not a fixed height - it grows when the appearance strip opens - so
   * this observes both bars rather than hardcoding an inset that would be wrong half
   * the time.
   */
  useEffect(() => {
    const win = windowRef.current;
    if (!win) return;
    const header = win.querySelector<HTMLElement>('.rts-header-group');
    const composer = win.querySelector<HTMLElement>('.rts-composer');
    if (!header || !composer) return;

    const sync = () => {
      win.style.setProperty('--chrome-top', `${header.offsetHeight}px`);
      win.style.setProperty('--chrome-bottom', `${composer.offsetHeight}px`);
    };
    sync();

    const observer = new ResizeObserver(sync);
    observer.observe(header);
    observer.observe(composer);
    return () => observer.disconnect();
  }, []);

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

  /* Keep the newest message in view as the keyboard takes its space, the way every
     chat app does - otherwise the conversation stays where it was and the last thing
     said ends up behind the keyboard. */
  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const stick = () => messagesEndRef.current?.scrollIntoView({ block: 'end' });
    viewport.addEventListener('resize', stick);
    return () => viewport.removeEventListener('resize', stick);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Flipping the rule does not restart the game - the chain survives, and the new rule
  // governs every word from here on. The bot just says so.
  // The AI calls the flip, and spells out what actually changed. Announce outside the
  // state updater - StrictMode invokes updaters twice, which would post the line twice.
  const toggleReverse = useCallback(async () => {
    const next = !reverse;
    setReverse(next);
    setMessages(m => [...m, { text: '', isUser: false }]);
    await announce(
      next
        ? "new rules... every word has to start with r t or s now, no other letters allowed"
        : "new rules... back to normal. no word can start with r, t or s"
    );
  }, [reverse]);

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

  const toggleThoughts = useCallback(() => {
    setShowThoughtProcess(prev => !prev);
  }, []);

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
        reverse={{ on: reverse, toggle: toggleReverse }}
        theme={{ on: isDark, toggle: toggleTheme }}
        thoughts={{ on: showThoughtProcess, toggle: toggleThoughts }}
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
        clock={<TurnTimer deadline={deadline} duration={TURN_MS}
                          onExpire={handleExpire} />}
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
          {messages.map((message, index) => (
            <div
              key={index}
              // `is-tapped` is what reveals the thumbs on touch, where there is no hover.
              className={`rts-msg ${message.isUser ? 'is-user' : 'is-bot'}${tapped === index ? ' is-tapped' : ''}`}
              onClick={message.link ? () => setTapped(t => (t === index ? null : index)) : undefined}
              ref={!message.isUser && index === messages.length - 1 ? latestBotMessageRef : null}
            >
              <div className="rts-msg-body">
                {message.isUser && message.showQuestionMark && (
                  <div className="question-mark-circle">
                    ?
                  </div>
                )}
                <div className={`rts-bubble${message.isUser ? ' is-user' : ''}`}>
                  {/* Dots while the request is in flight and while the train of thought
                      is still narrowing down - but not once streamed text has started
                      landing in this bubble, which replaces them. */}
                  {(message.pending && !message.streaming)
                   || (!message.isUser && index === messages.length - 1
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
                {message.link && (
                  <Rating
                    value={message.rating}
                    onRate={(r) => rate(index, message.link!, r)}
                  />
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
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
      </div>
    </div>
  );
}

export default Chat;
