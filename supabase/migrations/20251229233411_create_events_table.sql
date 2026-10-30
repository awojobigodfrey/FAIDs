/*
  # Create events table for intrusion detection system

  1. New Tables
    - `events`
      - `id` (uuid, primary key) - Unique event identifier
      - `event_type` (text) - Type of event: 'intrusion' or 'recognized'
      - `reason` (text) - Reason for classification: 'mask_detected', 'unknown_face', or 'recognized_face'
      - `person_name` (text, nullable) - Name of recognized person (null for intrusions)
      - `image_url` (text) - Azure Blob Storage URL for the captured image
      - `confidence` (numeric, nullable) - Confidence score from Azure AI
      - `timestamp` (timestamptz) - When the event occurred
      - `created_at` (timestamptz) - Record creation timestamp

  2. Security
    - Enable RLS on `events` table
    - Add policy for public read access (no auth required for dashboard)
    - Add policy for service role to insert events
*/

CREATE TABLE IF NOT EXISTS events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type text NOT NULL CHECK (event_type IN ('intrusion', 'recognized')),
  reason text NOT NULL CHECK (reason IN ('mask_detected', 'unknown_face', 'recognized_face')),
  person_name text,
  image_url text NOT NULL,
  confidence numeric,
  timestamp timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);

ALTER TABLE events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read access to events"
  ON events FOR SELECT
  TO anon
  USING (true);

CREATE POLICY "Allow service role to insert events"
  ON events FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);