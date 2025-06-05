import React from 'react';
import { useState, useRef, useEffect } from 'react';
import './ChatBox.css';

interface Message {
  text: string;
  isUser: boolean;
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
}

function ChatBox() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const [currentTrainOfThought, setCurrentTrainOfThought] = useState<string[]>([]);
  const [wordPositions, setWordPositions] = useState<Array<{x: number, y: number, rotate: number, scale: number}>>([]);
  const [animatingWords, setAnimatingWords] = useState<WordState[]>([]);
  const [isAnimating, setIsAnimating] = useState(false);
  const [serverData, setServerData] = useState<ServerResponse | null>(null);
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    setMessages(prev => [...prev, { text: inputText, isUser: true }]);
    setInputText('');
    
    try {
      const response = await fetch('http://localhost:5000/echo', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: inputText }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ServerResponse = await response.json();
      setServerData(data);
      console.log('Server Response:', data);
      
      if (data.train_of_thought && Array.isArray(data.train_of_thought)) {
        if (data.train_of_thought.length > 0) {
          setCurrentTrainOfThought(data.train_of_thought[0]);
        } else {
          setCurrentTrainOfThought([]);
        }
      }

      setMessages(prev => [...prev, { 
        text: data.response || "Sorry, something went wrong", 
        isUser: false 
      }]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { 
        text: "Sorry, I encountered an error. Please try again.", 
        isUser: false 
      }]);
      setCurrentTrainOfThought([]);
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

  useEffect(() => {
    if (!serverData?.train_of_thought || !Array.isArray(serverData.train_of_thought)) return;
    
    const animate = async () => {
      setIsAnimating(true);
      const seenWords = new Set<string>();
      
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

          await new Promise(resolve => setTimeout(resolve, 50));
        }

        const wordsToRemove = currentList.filter(word => !nextList.includes(word));
        
        for (const word of wordsToRemove) {
          setAnimatingWords(prev => 
            prev.map(w => w.word === word ? { ...w, opacity: 0 } : w)
          );
          await new Promise(resolve => setTimeout(resolve, 50));
        }

        await new Promise(resolve => setTimeout(resolve, 50));
        setAnimatingWords(prev => prev.filter(w => nextList.includes(w.word)));
      }
    };

    animate();
    
    return () => {
      setAnimatingWords([]);
      setIsAnimating(false);
    };
  }, [serverData?.train_of_thought]);

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
                      Math.min(Math.max(wordState.position.x, 0), 260) // Constrain to content area
                    }px, ${
                      Math.min(Math.max(wordState.position.y, 0), 430) // Constrain to content area
                    }px) rotate(${wordState.position.rotate}deg) scale(${wordState.position.scale})`,
                    opacity: wordState.opacity,
                    transition: 'opacity 0.3s ease, transform 0.3s ease',
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
              <div style={{
                maxWidth: '100%',
                padding: '8px 12px',
                borderRadius: '12px',
                backgroundColor: message.isUser ? '#FFAC1C' : '#E9E9EB',
                color: message.isUser ? 'white' : 'black'
              }}>
                {message.text}
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