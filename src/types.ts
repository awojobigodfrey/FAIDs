export interface Event {
  id: string;
  event_type: 'intrusion' | 'recognized';
  reason: 'mask_detected' | 'unknown_face' | 'recognized_face';
  person_name: string | null;
  image_url: string;
  confidence: number | null;
  timestamp: string;
  created_at: string;
}

export interface Stats {
  total_intrusions: number;
  total_recognized: number;
}
