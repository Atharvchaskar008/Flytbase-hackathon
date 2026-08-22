import React, { useState } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface VideoPlayerProps {
  videoUrl: string;
  eventId?: string;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, eventId }) => {
  const [error, setError] = useState<string | null>(null);

  return (
    <div style={{ border: '1px solid #ccc', padding: '15px' }}>
      <h2>Video Clip</h2>
      {eventId && <p>Event ID: {eventId}</p>}
      <div style={{ marginTop: '10px' }}>
        <video width="640" height="360" controls onError={() => setError('Failed to load video')}>
          <source src={videoUrl} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>
      <p>URL: {videoUrl}</p>
      {error && <p style={{ color: 'red' }}>{error}</p>}
    </div>
  );
};

export default VideoPlayer;