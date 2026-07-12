import React from 'react';
import { useState, useRef, useEffect, useCallback } from 'react';
import './chat.css';
import Header from './Header';

interface Message {
  text: string;
  isUser: boolean;
  showQuestionMark?: boolean;
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
  // Announce outside the state updater: StrictMode invokes updaters twice, so queuing
  // the message in there posts it twice.
  const toggleReverse = useCallback(() => {
    const next = !reverse;
    setReverse(next);
    setMessages(m => [...m, {
      text: next ? 'flipped. rts words only now' : 'back to normal. no rts',
      isUser: false,
    }]);
  }, [reverse]);

  const toggleTheme = useCallback(() => {
    setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  const toggleThoughts = useCallback(() => {
    setShowThoughtProcess(prev => !prev);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    setMessages(prev => [...prev, { text: inputText, isUser: true }]);
    const userInput = inputText;
    setInputText('');

    try {
      const response = await fetch(`${API_URL}/echo`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userInput, reverse: reverseRef.current }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data: ServerResponse = await response.json();

      if (data.response_code === 'UNRELATED') {
        setMessages(prev => {
          const newMessages = [...prev];
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].isUser) {
              newMessages[i].showQuestionMark = true;
              break;
            }
          }
          return [...newMessages, { text: data.response, isUser: false }];
        });
      } else {
        setMessages(prev => [...prev, { text: data.response, isUser: false }]);
      }

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
      setMessages(prev => [...prev, {
        text: "?",
        isUser: false
      }]);
    }
  };

  useEffect(() => {
    let mounted = true;

    const initializeChat = async () => {
      if (!mounted) return;

      await fetch(`${API_URL}/reset`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reverse: reverseRef.current }),
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
              ref={!message.isUser && index === messages.length - 1 ? latestBotMessageRef : null}
              style={{
                display: 'flex',
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
                  {(!message.isUser && index === messages.length - 1) ? (
                    isTyping && showThoughtProcess ? (
                      <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    ) : isTextAnimating ? (
                      animatedText
                    ) : (
                      message.text
                    )
                  ) : (
                    message.text
                  )}
                </div>
              </div>
            </div>
          ))}
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
