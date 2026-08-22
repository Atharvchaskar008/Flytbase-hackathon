import React, { useState } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface Video {
  id: string;
  filename: string;
  uploaded_at: string;
}

interface Event {
  id: string;
  type: string;
  start_time: number;
  end_time: number;
}

interface TimelineItem {
  timestamp: number;
  event_id: string;
  description: string;
}

const Dashboard: React.FC = () => {
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [videoId, setVideoId] = useState('');
  const [processResult, setProcessResult] = useState<string | null>(null);
  const [videos, setVideos] = useState<Video[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [queryText, setQueryText] = useState('');
  const [queryResult, setQueryResult] = useState<string | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageSearchResult, setImageSearchResult] = useState<string | null>(null);
  const [eventId, setEventId] = useState('');
  const [clipUrl, setClipUrl] = useState<string | null>(null);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoFile) return;
    const formData = new FormData();
    formData.append('video', videoFile);
    const res = await fetch(`${API_BASE}/upload/video`, { method: 'POST', body: formData });
    const data = await res.json();
    setUploadResult(JSON.stringify(data, null, 2));
    setVideoId(data.video_id || '');
  };

  const handleProcess = async () => {
    if (!videoId) return;
    const res = await fetch(`${API_BASE}/process/${videoId}`, { method: 'POST' });
    const data = await res.json();
    setProcessResult(JSON.stringify(data, null, 2));
  };

  const handleListVideos = async () => {
    const res = await fetch(`${API_BASE}/videos`);
    const data = await res.json();
    setVideos(data);
  };

  const handleGetEvents = async (id: string) => {
    const res = await fetch(`${API_BASE}/videos/${id}/events`);
    const data = await res.json();
    setEvents(data);
  };

  const handleGetTimeline = async (id: string) => {
    const res = await fetch(`${API_BASE}/videos/${id}/timeline`);
    const data = await res.json();
    setTimeline(data);
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch(`${API_BASE}/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: queryText })
    });
    const data = await res.json();
    setQueryResult(JSON.stringify(data, null, 2));
  };

  const handleImageSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!imageFile) return;
    const formData = new FormData();
    formData.append('image', imageFile);
    const res = await fetch(`${API_BASE}/image-search`, { method: 'POST', body: formData });
    const data = await res.json();
    setImageSearchResult(JSON.stringify(data, null, 2));
  };

  const handleGetClip = async () => {
    if (!eventId) return;
    const res = await fetch(`${API_BASE}/clip/${eventId}`);
    const data = await res.json();
    setClipUrl(data.clip_url || null);
  };

  return (
    <div style={{ padding: '20px', maxWidth: '1200px' }}>
      <h1>Backend API Testing Dashboard</h1>

      {/* 1. Upload Video */}
      <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
        <h2>1. Upload Video</h2>
        <form onSubmit={handleUpload}>
          <input type="file" accept="video/*" onChange={(e) => setVideoFile(e.target.files?.[0] || null)} />
          <button type="submit">Upload</button>
        </form>
        {uploadResult && <pre>{uploadResult}</pre>}
      </div>

      {/* 2. Process Video */}
      <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
        <h2>2. Process Video</h2>
        <div>
          <input
            type="text"
            placeholder="Enter video_id"
            value={videoId}
            onChange={(e) => setVideoId(e.target.value)}
          />
          <button onClick={handleProcess}>Process</button>
        </div>
        {processResult && <pre>{processResult}</pre>}
      </div>

      {/* 3. List Videos */}
      <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
        <h2>3. List Videos</h2>
        <button onClick={handleListVideos}>Get Videos</button>
        {videos.length > 0 && (
          <div>
            <ul>
              {videos.map((v) => (
                <li key={v.id}>
                  {v.filename} ({v.id}) - {new Date(v.uploaded_at).toLocaleString()}
                </li>
              ))}
            </ul>
            <div style={{ marginTop: '10px' }}>
              {videos.map((v) => (
                <button key={v.id} onClick={() => handleGetEvents(v.id)} style={{ marginRight: '5px' }}>
                  Load Events: {v.id}
                </button>
              ))}
              {videos.map((v) => (
                <button key={v.id} onClick={() => handleGetTimeline(v.id)}>
                  Load Timeline: {v.id}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Events Display */}
      {events.length > 0 && (
        <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
          <h2>Events</h2>
          <pre>{JSON.stringify(events, null, 2)}</pre>
        </div>
      )}

      {/* Timeline Display */}
      {timeline.length > 0 && (
        <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
          <h2>Timeline</h2>
          <pre>{JSON.stringify(timeline, null, 2)}</pre>
        </div>
      )}

      {/* 4. Search */}
      <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
        <h2>4. Search</h2>
        <form onSubmit={handleQuery}>
          <textarea
            placeholder="Enter search query"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            rows={3}
            style={{ width: '100%', maxWidth: '500px' }}
          />
          <button type="submit">Search</button>
        </form>
        {queryResult && <pre>{queryResult}</pre>}
      </div>

      {/* 5. Image Search */}
      <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
        <h2>5. Image Search</h2>
        <form onSubmit={handleImageSearch}>
          <input type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] || null)} />
          <button type="submit">Search Image</button>
        </form>
        {imageSearchResult && <pre>{imageSearchResult}</pre>}
      </div>

      {/* 6. Clip Retrieval */}
      <div style={{ border: '1px solid #ccc', padding: '15px', marginBottom: '20px' }}>
        <h2>6. Clip Retrieval</h2>
        <div>
          <input
            type="text"
            placeholder="Enter event_id"
            value={eventId}
            onChange={(e) => setEventId(e.target.value)}
          />
          <button onClick={handleGetClip}>Get Clip</button>
        </div>
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
    </div>
  );
};

export default Dashboard;