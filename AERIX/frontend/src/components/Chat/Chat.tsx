import React, { useState } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

interface Props {
  videoId: string;
}

const Chat: React.FC<Props> = ({ videoId }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    
    const userMsg: Message = { role: 'user', content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input, video_id: videoId })
      });
      const data = await res.json();
      const assistantMsg: Message = { role: 'assistant', content: JSON.stringify(data, null, 2) };
      setMessages((prev) => [...prev, assistantMsg]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', padding: '15px', height: '500px', display: 'flex', flexDirection: 'column' }}>
      <h2>Chat: Video {videoId}</h2>
      <div style={{ flex: 1, overflow: 'auto', marginBottom: '10px' }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ marginBottom: '10px', padding: '8px', background: msg.role === 'user' ? '#e0e0e0' : '#f0f0f0' }}>
            <strong>{msg.role}:</strong>
            <pre style={{ margin: '5px 0 0', whiteSpace: 'pre-wrap' }}>{msg.content}</pre>
          </div>
        ))}
      </div>
      <form onSubmit={sendMessage}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the video..."
          rows={3}
          style={{ width: '100%', maxWidth: '500px', marginRight: '10px' }}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>
    </div>
  );
};

export default Chat;