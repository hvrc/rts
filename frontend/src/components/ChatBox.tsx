import React from 'react';
import { useState, useRef, useEffect } from 'react';
import './ChatBox.css';

interface Message {
  text: string;
  isUser: boolean;
  showQuestionMark?: boolean;  // Add this
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
  response_code: string;  // Add this
}

function ChatBox() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [currentTrainOfThought, setCurrentTrainOfThought] = useState<string[]>([]);
  const [wordPositions, setWordPositions] = useState<Array<{x: number, y: number, rotate: number, scale: number}>>([]);
  const [animatingWords, setAnimatingWords] = useState<WordState[]>([]);
  const [isAnimating, setIsAnimating] = useState(false);
  const [serverData, setServerData] = useState<ServerResponse | null>(null);
  const [isTyping, setIsTyping] = useState(false); // New state for tracking typing indicator
  const [animatedText, setAnimatedText] = useState("");
  const [isTextAnimating, setIsTextAnimating] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const latestBotMessageRef = useRef<HTMLDivElement>(null);
  const chatBoxRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Update the handleSubmit function
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    // Add user message first without question mark
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

      // If response is UNRELATED, update the last user message to show question mark
      if (data.response_code === 'UNRELATED') {
        setMessages(prev => {
          const newMessages = [...prev];
          // Find the last user message and add question mark
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].isUser) {
              newMessages[i].showQuestionMark = true;
              break;
            }
          }
          return [...newMessages, { text: data.response, isUser: false }];
        });
      } else {
        // Normal bot response without question mark
        setMessages(prev => [...prev, { text: data.response, isUser: false }]);
      }

      // Rest of the handling remains the same
      if (data.train_of_thought && data.train_of_thought.length > 0) {
        setServerData(data);
        setIsTyping(true);
      } else {
        setIsTextAnimating(true);
        setAnimatedText("");
        for (let i = 0; i < data.response.length; i++) {
          setAnimatedText(prev => prev + data.response[i]);
          await new Promise(resolve => setTimeout(resolve, 50));
        }
        setIsTextAnimating(false);
      }

    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { 
        text: "Sorry, I encountered an error. Please try again.", 
        isUser: false 
      }]);
    }
  };

  React.useEffect(() => {
    fetch('http://localhost:5000/reset', {
      method: 'POST',
    })
    .then(response => response.json())
    .catch(error => console.error('Error resetting game:', error));
  }, []);

  useEffect(() => {
    if (currentTrainOfThought.length > 0) {
      const newPositions = currentTrainOfThought.map(() => ({
        x: Math.random() * 260 - 35, // Span messages-container width (280px - 10px padding on each side)
        y: Math.random() * 430, // Span messages-container height (approx 430px)
        rotate: Math.random() * 30 - 15,
        scale: 0.8 + Math.random() * 0.4
      }));
      setWordPositions(newPositions);
    }
  }, [currentTrainOfThought]);

  // Update the animation effect
  useEffect(() => {
    if (!serverData?.train_of_thought || !Array.isArray(serverData.train_of_thought)) return;
    
    const animate = async () => {
      setIsAnimating(true);
      setIsTyping(true); // Start typing indicator
      
      for (let i = 0; i < serverData.train_of_thought.length - 1; i++) {
        const currentList = serverData.train_of_thought[i];
        const nextList = serverData.train_of_thought[i + 1];

        if (i === 0) {
          const positions = new Map(
            currentList.map(word => [word, {
              x: Math.random() * 260 - 35, // Span messages-container width
              y: Math.random() * 430, // Span messages-container height
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

        // Update the last iteration check in the animation effect
        if (i === serverData.train_of_thought.length - 2) {
          // Show the bot response first
          await new Promise(resolve => setTimeout(resolve, 500));
          setIsTyping(false); // Stop typing indicator
          
          // Animate the bot's response character by character
          await animateText(messages[messages.length - 1].text);
          
          // Wait a moment after text animation, then fade out last word
          await new Promise(resolve => setTimeout(resolve, 300));
          setAnimatingWords(prev => 
            prev.map(w => ({
              ...w,
              opacity: 0 // Fade out all remaining words
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
  }, [serverData?.train_of_thought]);

  // Update the animateText function
  const animateText = async (text: string) => {
    if (!text) return;
    
    setIsTextAnimating(true);
    setAnimatedText("");
    
    for (let i = 0; i < text.length; i++) {
      setAnimatedText(prev => prev + text[i]);
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    
    // Update the actual message text after animation
    setMessages(prev => {
      const newMessages = [...prev];
      newMessages[newMessages.length - 1].text = text;
      return newMessages;
    });
    
    setIsTextAnimating(false);
  };

  return (
    <div style={{ 
      position: 'absolute',
      width: '280px',
    }}>
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
          {isAnimating && (
            <div className="train-of-thought" style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%', // Match messages-container width
              height: '100%', // Match messages-container height
              pointerEvents: 'none',
              zIndex: 10, // Render in front of messages
              padding: '10px' // Match messages-container padding
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
                      wordState.opacity === 0 ? '2s' :  // longer fade out
                      wordState.opacity === 1 ? '1s' :  // normal fade in
                      '0.1s'                           // default
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
                {message.isUser && message.showQuestionMark && ( // Changed from message.isUser to !message.isUser
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
                    isTyping ? (
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
            placeholder="Message"
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
              padding: '8px 16px',
              borderRadius: '20px',
              backgroundColor: '#FFAC1C',
              color: 'white',
              border: 'none',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            ^
          </button>
        </form>
      </div>
    </div>
  );
}

export default ChatBox;