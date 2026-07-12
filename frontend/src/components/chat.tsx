import React from 'react';
import { useState, useRef, useEffect, useCallback } from 'react';
import './chat.css';
import Header from './Header';
import Rating from './Rating';
import { gameId, loadPrefs, ratePair, type Link, type Rating as RatingValue } from '../lib/prefs';

interface Message {
  text: string;
  isUser: boolean;
  showQuestionMark?: boolean;
  link?: Link;          // the leap the bot made (from -> to). only on a played word.
  rating?: RatingValue; // what the human thought of that leap.

  // Where the game boundary sits relative to this message. A loss message *ends* the
  // old game, so the divider goes under it. A restart message is the opening move of
  // the new game, so the divider goes above it.
  newGameAfter?: boolean;
  newGameBefore?: boolean;

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

type Theme = 'light' | 'dark';

const THEME_KEY = 'rts.theme';

function initialTheme(): Theme {
  const saved = localStorage.getItem(THEME_KEY);
  return saved === 'dark' ? 'dark' : 'light'; // light is the original look; it stays the default
}

function Chat() {
  const API_URL = import.meta.env.PROD
    ? 'https://backend-dot-rts0-462101.ue.r.appspot.com'
    : 'http://localhost:5001';

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

  // The three header toggles.
  const [showThoughtProcess, setShowThoughtProcess] = useState(false); // s
  const [theme, setTheme] = useState<Theme>(initialTheme);             // t
  const [reverse, setReverse] = useState(false);                       // r

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const latestBotMessageRef = useRef<HTMLDivElement>(null);
  const chatBoxRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  // `reverse` is read inside async handlers that would otherwise close over a stale
  // value; the ref always has the current one.
  const reverseRef = useRef(reverse);
  useEffect(() => { reverseRef.current = reverse; }, [reverse]);

  // Theme lives on <html> so index.css can drive every color from one attribute.
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Flipping the rule does not restart the game — the chain survives, and the new rule
  // governs every word from here on. The bot just says so.
  // The AI calls the flip, and spells out what actually changed. Announce outside the
  // state updater — StrictMode invokes updaters twice, which would post the line twice.
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

  const toggleTheme = useCallback(() => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  const toggleThoughts = useCallback(() => {
    setShowThoughtProcess(prev => !prev);
  }, []);

  /**
   * Swap the waiting bubble for the real reply. The placeholder is the one message in
   * flight, so land on it rather than appending — otherwise the dots would linger above
   * the answer.
   */
  const settlePending = useCallback((botMessage: Message, flagUnrelated = false) => {
    setMessages(prev => {
      const next = [...prev];
      const at = next.map(m => !!m.pending).lastIndexOf(true);
      if (at === -1) {
        next.push(botMessage);       // no placeholder (shouldn't happen) — don't lose the reply
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

    // The bot starts "thinking" the instant you hit send, in every mode — not only when
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
      // when there is something worth rating.
      const restarted = data.response_code === 'RESTART';
      const botMessage: Message = {
        text: data.response,
        isUser: false,
        link: data.link,
        newGameBefore: data.new_game && restarted,   // this word opens the new game
        newGameAfter: data.new_game && !restarted,   // a loss — this closed the old one
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
      // Settle, don't append — otherwise the dots spin forever above the "?".
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
    <div style={{
      position: 'fixed',
      width: '280px',
      height: '100%',
      maxHeight: '480px',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <Header
        reverse={{ on: reverse, toggle: toggleReverse }}
        theme={{ on: theme === 'dark', toggle: toggleTheme }}
        thoughts={{ on: showThoughtProcess, toggle: toggleThoughts }}
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
              className="rts-msg"
              ref={!message.isUser && index === messages.length - 1 ? latestBotMessageRef : null}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: message.isUser ? 'flex-end' : 'flex-start',
                marginBottom: '10px'
              }}
            >
              <div style={{ position: 'relative' }}>
                {message.isUser && message.showQuestionMark && (
                  <div className="question-mark-circle">
                    ?
                  </div>
                )}
                <div style={{
                  maxWidth: '100%',
                  padding: '8px 12px',
                  borderRadius: '12px',
                  backgroundColor: message.isUser ? 'var(--bubble-user-bg)' : 'var(--bubble-bot-bg)',
                  color: message.isUser ? 'var(--bubble-user-text)' : 'var(--bubble-bot-text)',
                  transition: 'background-color 0.25s ease, color 0.25s ease'
                }}>
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
              </div>
              {message.link && (
                <Rating
                  value={message.rating}
                  onRate={(r) => rate(index, message.link!, r)}
                />
              )}
            </div>
          )).flatMap((el, index) => {
            // The history stays on screen across games, so words legitimately repeat
            // across this line. Mark the boundary or it just reads like a bug.
            const divider = <div className="rts-newgame" key={`ng-${index}`}>new game</div>;
            const msg = messages[index];
            if (msg.newGameBefore) return [divider, el];
            if (msg.newGameAfter) return [el, divider];
            return [el];
          })}
          <div ref={messagesEndRef} />
        </div>
        <form
          onSubmit={handleSubmit}
          style={{
            display: 'flex',
            gap: '8px',
            padding: '10px',
            position: 'relative',
            zIndex: 3,
            backgroundColor: 'var(--surface)',
            transition: 'background-color 0.25s ease'
          }}
        >
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder=""
            style={{
              flex: 1,
              padding: '8px 12px',
              borderRadius: '20px',
              border: '1px solid var(--input-border)',
              backgroundColor: 'var(--input-bg)',
              color: 'var(--input-text)',
              outline: 'none',
              fontSize: window.innerWidth <= 768 ? '16px' : '14px',
              WebkitAppearance: 'none',
              touchAction: 'manipulation',
              userSelect: 'text',
              transition: 'background-color 0.25s ease, color 0.25s ease, border-color 0.25s ease'
            }}
          />
          <button
            type="submit"
            style={{
              width: '25px',
              height: '25px',
              padding: 0,
              borderRadius: '50%',
              backgroundColor: 'var(--bubble-user-bg)',
              color: 'var(--bubble-user-text)',
              border: 'none',
              outline: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginTop: '2px'
            }}
          >
          </button>
        </form>
      </div>
    </div>
  );
}

export default Chat;
