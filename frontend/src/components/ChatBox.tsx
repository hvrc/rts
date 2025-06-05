import React from 'react';
import { useState, useRef, useEffect } from 'react';
import './ChatBox.css';  // Add this import

interface Message {
  text: string;
  isUser: boolean;
}

function ChatBox() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

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

      const data = await response.json();
      
      // Log the entire response data
      console.log('Server Response:', {
        word: inputText,
        response: data.response,
        train_of_thought: data.train_of_thought
      });

      setMessages(prev => [...prev, { text: data.response, isUser: false }]);
    } catch (error) {
      console.error('Error:', error);
    }
  };

  React.useEffect(() => {
    // Reset game when component mounts
    fetch('http://localhost:5000/reset', {
      method: 'POST',
    })
    .then(response => response.json())
    .catch(error => console.error('Error resetting game:', error));
  }, []);

  return (
    <div style={{ 
      width: '280px',
      height: '480px',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div className="messages-container">
        {messages.map((message, index) => (
          <div
            key={index}
            style={{
              display: 'flex',
              justifyContent: message.isUser ? 'flex-end' : 'flex-start',
              marginBottom: '10px'
            }}
          >
            <div style={{
              maxWidth: '70%',
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
          padding: '10px'
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
  );
}

export default ChatBox;
