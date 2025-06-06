import React from 'react';
import { useState, useRef, useEffect } from 'react';
import './Chat.css';
import Logo from './Logo';

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

function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [currentTrainOfThought, setCurrentTrainOfThought] = useState<string[]>([]);
  const [wordPositions, setWordPositions] = useState<Array<{x: number, y: number, rotate: number, scale: number}>>([]);
  const [animatingWords, setAnimatingWords] = useState<WordState[]>([]);
  const [isAnimating, setIsAnimating] = useState(false);
  const [serverData, setServerData] = useState<ServerResponse | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [animatedText, setAnimatedText] = useState("");
  const [isTextAnimating, setIsTextAnimating] = useState(false);
  const [showThoughtProcess, setShowThoughtProcess] = useState(false);
  const [lastProcessedMessage, setLastProcessedMessage] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const latestBotMessageRef = useRef<HTMLDivElement>(null);
  const chatBoxRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const trainOfThoughtButtonRef = useRef<HTMLDivElement>(null);
  const darkModeButtonRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    setMessages(prev => [...prev, { text: inputText, isUser: true }]);
    const userInput = inputText;
    setInputText('');
    
    try {
      const response = await fetch('http://localhost:5000/echo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: userInput }),
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

      await fetch('http://localhost:5000/reset', {
        method: 'POST',
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

  const HeaderComponent = () => {
    const [isDarkMode, setIsDarkMode] = useState(false);

    const buttonContainerStyle = {
      display: 'flex',
      gap: '8px',
      alignItems: 'center',
      marginRight: '45px',
      marginTop: '10px'
    };

    const buttonStyle = {
      width: '25px',
      height: '25px',
      padding: 0,
      minWidth: '25px',
      minHeight: '25px',
      borderRadius: '50%',
      backgroundColor: '#E9E9EB',
      color: '#666',
      border: 'none',
      outline: 'none',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: '14px',
      transition: 'background-color 0.3s ease',
      position: 'relative'
    } as React.CSSProperties;

    const labelStyle = {
      position: 'absolute',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      borderRadius: '50%',
      cursor: 'pointer',
      transition: 'background-color 0.3s ease'
    } as React.CSSProperties;

    // Update button colors based on state
    useEffect(() => {
      if (trainOfThoughtButtonRef.current) {
        trainOfThoughtButtonRef.current.style.backgroundColor = showThoughtProcess ? '#CCCCFF' : '#E9E9EB';
      }
      if (darkModeButtonRef.current) {
        darkModeButtonRef.current.style.backgroundColor = isDarkMode ? '#CCCCFF' : '#E9E9EB';
      }
    }, [showThoughtProcess, isDarkMode]);

    return (
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        width: '100%',
        padding: '4px 10px 16px 30px'
      }}>
        <Logo />
        <div style={buttonContainerStyle}>
          {/* Train of Thought button (left) */}
          <div style={{ position: 'relative' }}>
            <div
              ref={trainOfThoughtButtonRef}
              style={{
                ...buttonStyle,
                backgroundColor: showThoughtProcess ? '#CCCCFF' : '#E9E9EB'
              }}
            >
              <input
                type="checkbox"
                id="trainOfThoughtToggle"
                style={{
                  opacity: 0,
                  position: 'absolute',
                  width: '100%',
                  height: '100%',
                  margin: 0,
                  cursor: 'pointer'
                }}
                checked={showThoughtProcess}
                onChange={(e) => {
                  setShowThoughtProcess(e.currentTarget.checked);
                }}
                onMouseOver={(e) => {
                  const container = e.currentTarget.parentElement;
                  if (container && !showThoughtProcess) {
                    container.style.backgroundColor = '#D3D3D3';
                  }
                }}
                onMouseOut={(e) => {
                  const container = e.currentTarget.parentElement;
                  if (container && !showThoughtProcess) {
                    container.style.backgroundColor = '#E9E9EB';
                  }
                }}
              />
              <label htmlFor="trainOfThoughtToggle" style={labelStyle} title="Train of Thought"></label>
            </div>
          </div>

          {/* Dark Mode button (right) */}
          {/* <div style={{ position: 'relative' }}>
            <div
              ref={darkModeButtonRef}
              style={{
                ...buttonStyle,
                backgroundColor: isDarkMode ? '#CCCCFF' : '#E9E9EB'
              }}
            >
              <input
                type="checkbox"
                id="darkModeToggle"
                style={{
                  opacity: 0,
                  position: 'absolute',
                  width: '100%',
                  height: '100%',
                  margin: 0,
                  cursor: 'pointer'
                }}
                checked={isDarkMode}
                onChange={(e) => {
                  setIsDarkMode(e.currentTarget.checked);
                }}
                onMouseOver={(e) => {
                  const container = e.currentTarget.parentElement;
                  if (container && !isDarkMode) {
                    container.style.backgroundColor = '#D3D3D3';
                  }
                }}
                onMouseOut={(e) => {
                  const container = e.currentTarget.parentElement;
                  if (container && !isDarkMode) {
                    container.style.backgroundColor = '#E9E9EB';
                  }
                }}
              />
              <label htmlFor="darkModeToggle" style={labelStyle} title="Dark Mode"></label>
            </div>
          </div> */}
        </div>
      </div>
    );
  };

  return (
    <div style={{ 
      position: 'absolute',
      width: '280px',
    }}>
      <HeaderComponent />
      <div 
        ref={chatBoxRef}
        style={{ 
          width: '280px',
          height: '480px',
          display: 'flex',
          flexDirection: 'column',
          position: 'relative'
        }}
      >
        <div 
          ref={messagesContainerRef} 
          className="messages-container"
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
                    color: '#666',
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
                  backgroundColor: message.isUser ? '#FFAC1C' : '#E9E9EB',
                  color: message.isUser ? 'white' : 'black'
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
            zIndex: 3
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
              border: '1px solid #E9E9EB',
              outline: 'none'
            }}
          />
          <button
            type="submit"
            style={{
              width: '25px',
              height: '25px',
              padding: 0,
              borderRadius: '50%',
              backgroundColor: '#FFAC1C',
              color: 'white',
              border: 'none',
              outline: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginTop: '2px'  // Added this line to nudge button down
            }}
          >
          </button>
        </form>
      </div>
    </div>
  );
}

export default Chat;