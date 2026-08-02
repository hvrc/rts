import React from 'react';
import { useState, useRef, useEffect, useCallback } from 'react';
import './chat.css';
import '../skins/aqua.css';
import Header from './Header';
import Rating from './Rating';
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
}

type Skin = 'aqua' | 'flat';

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
  const [animatedText, setAnimatedText] = useState("");
  const [isTextAnimating, setIsTextAnimating] = useState(false);
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
    await animateText(
      next
        ? "new rules... every word has to START with r, t or s now. anything else and you're out"
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

    try {
      const response = await fetch(`${API_URL}/echo`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userInput,
          game_id: gameId(),
          reverse: reverseRef.current,
          preferences: loadPrefs(),   // taste travels with every turn
        }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data: ServerResponse = await response.json();

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

      if (showThoughtProcess && data.train_of_thought && data.train_of_thought.length > 0 && userInput !== lastProcessedMessage) {
        setServerData(data);
        setIsTyping(true);
        setLastProcessedMessage(userInput);
      } else {
        setIsTextAnimating(true);
        setAnimatedText("");
        for (let i = 0; i < data.response.length; i++) {
          setAnimatedText(prev => prev + data.response[i]);
          await new Promise(resolve => setTimeout(resolve, 50));
        }
        setIsTextAnimating(false);
        setLastProcessedMessage(userInput);
      }

    } catch (error) {
      console.error('Error:', error);
      // Settle, don't append - otherwise the dots spin forever above the "?".
      settlePending({ text: "?", isUser: false });
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

      for (const message of welcomeMessages) {
        if (!mounted) break;

        setMessages(prev => [...prev, { text: "", isUser: false }]);

        setIsTextAnimating(true);
        setAnimatedText("");
        for (let i = 0; i < message.length; i++) {
          if (!mounted) break;
          setAnimatedText(prev => prev + message[i]);
          await new Promise(resolve => setTimeout(resolve, 25));
        }

        setMessages(prev => {
          const newMessages = [...prev];
          newMessages[newMessages.length - 1].text = message;
          return newMessages;
        });
        setIsTextAnimating(false);

        await new Promise(resolve => setTimeout(resolve, 100));
      }
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

          await animateText(messages[messages.length - 1].text);

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

  const animateText = async (text: string) => {
    if (!text) return;

    setIsTextAnimating(true);
    setAnimatedText("");

    for (let i = 0; i < text.length; i++) {
      setAnimatedText(prev => prev + text[i]);
      await new Promise(resolve => setTimeout(resolve, 25));
    }

    setMessages(prev => {
      const newMessages = [...prev];
      newMessages[newMessages.length - 1].text = text;
      return newMessages;
    });

    setIsTextAnimating(false);
  };

  return (
    <div
      ref={windowRef}
      className={`rts-window${dragging ? ' is-dragging' : ''}${resizing ? ' is-resizing' : ''}`}
      style={{
        position: 'fixed',
        display: 'flex',
        flexDirection: 'column',
        // Untouched: 280 wide and as tall as fits, capped at 480. Once resized,
        // both become explicit and the cap no longer applies.
        width: size ? size.w : 280,
        height: size ? size.h : '100%',
        ...(size ? null : { maxHeight: 480 }),
        // Once dragged, explicit coordinates replace the CSS centering.
        ...(pos ? { left: pos.x, top: pos.y, transform: 'none' } : null),
      }}
    >
      {RESIZE_EDGES.map((edge) => (
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
        onDragStart={startDrag}
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
                  {/* thinking: while the request is in flight (any mode), and while the
                      train of thought is still narrowing down to its pick */}
                  {message.pending || (!message.isUser && index === messages.length - 1
                                       && isTyping && showThoughtProcess) ? (
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  ) : (!message.isUser && index === messages.length - 1) ? (
                    isTextAnimating ? animatedText : message.text
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
