import React, { useState } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface TimelineItem {
  timestamp: number;
  event_id: string;
  description: string;
}

interface Props {
  videoId: string;
}

const Timeline: React.FC<Props> = ({ videoId }) => {
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadTimeline = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/videos/${videoId}/timeline`);
      const data = await res.json();
      setTimeline(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', padding: '15px' }}>
      <h2>Timeline for Video: {videoId}</h2>
      <button onClick={loadTimeline} disabled={loading}>
        {loading ? 'Loading...' : 'Load Timeline'}
      </button>
      <pre>{JSON.stringify(timeline, null, 2)}</pre>
    </div>
  );
};

export default Timeline;