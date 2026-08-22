import React, { useState } from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface ImageSearchResult {
  matches: Array<{
    image_id: string;
    similarity: number;
    metadata: Record<string, unknown>;
  }>;
}

interface Props {
  onResult?: (result: ImageSearchResult) => void;
}

const ImageSearch: React.FC<Props> = ({ onResult }) => {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImageSearchResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!imageFile) return;
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('image', imageFile);
      const res = await fetch(`${API_BASE}/image-search`, { method: 'POST', body: formData });
      const data = await res.json();
      setResult(data);
      onResult?.(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ border: '1px solid #ccc', padding: '15px' }}>
      <h2>Image Search</h2>
      <form onSubmit={handleSearch}>
        <input type="file" accept="image/*" onChange={(e) => setImageFile(e.target.files?.[0] || null)} />
        <button type="submit" disabled={loading}>
          {loading ? 'Searching...' : 'Search'}
        </button>
      </form>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
};

export default ImageSearch;