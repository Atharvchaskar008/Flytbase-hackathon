import React, { useState } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface ClipResponse {
  clip_url: string;
}

interface Props {
  eventId: string;
  onClipReceived?: (url: string) => void;
}

const ClipRetrieval: React.FC<Props> = ({ eventId, onClipReceived }) => {
  const [clipUrl, setClipUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleGetClip = async () => {
    if (!eventId) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/clip/${eventId}`);
      const data: ClipResponse = await res.json();
      setClipUrl(data.clip_url || null);
      onClipReceived?.(data.clip_url || '');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', padding: '15px' }}>
      <h2>Clip Retrieval</h2>
      <p>Event ID: {eventId}</p>
      <button onClick={handleGetClip} disabled={loading}>
        {loading ? 'Fetching...' : 'Get Clip'}
      </button>
      {clipUrl && (
        <div style={{ marginTop: '10px' }}>
          <video width="640" height="360" controls>
            <source src={clipUrl} type="video/mp4" />
            Your browser does not support the video tag.
          </video>
          <p>Clip URL: {clipUrl}</p>
        </div>
      )}
    </div>
  );
};

export default ClipRetrieval;