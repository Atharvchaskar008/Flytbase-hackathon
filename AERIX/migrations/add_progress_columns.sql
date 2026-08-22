-- Migration: Add progress tracking columns to videos table
-- Phase 10 - Processing Status

ALTER TABLE videos ADD COLUMN IF NOT EXISTS progress INTEGER NOT NULL DEFAULT 0;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS progress_message VARCHAR(255);
ALTER TABLE videos ADD COLUMN IF NOT EXISTS frames_total INTEGER;
ALTER TABLE videos ADD COLUMN IF NOT EXISTS frames_processed INTEGER;

-- Add constraint for progress range
ALTER TABLE videos ADD CONSTRAINT check_progress_range CHECK (progress >= 0 AND progress <= 100);

-- Create index for status queries
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_progress ON videos(progress);
