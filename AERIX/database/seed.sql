-- TRACE seed data

-- Insert a default camera for testing
INSERT INTO cameras (id, name, location, rtsp_url, status, created_at)
VALUES (
    'a0000000-0000-0000-0000-000000000001'::uuid,
    'Test Camera',
    'Test Location',
    'rtsp://test',
    'active',
    NOW()
)
ON CONFLICT (id) DO NOTHING;
