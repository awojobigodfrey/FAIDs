import type { Event, Stats } from '../types';

// Read API URL from Vercel environment variable, fallback to local/codespace URL
const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://vigilant-space-telegram-9wjjr7pj6wxc6w-8000.app.github.dev/api';

export const api = {
  async getStats(): Promise<Stats> {
    const response = await fetch(`${API_BASE_URL}/stats`);
    if (!response.ok) throw new Error('Failed to fetch stats');
    return response.json();
  },

  async getEvents(limit: number = 100): Promise<Event[]> {
    const response = await fetch(`${API_BASE_URL}/events?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to fetch events');
    return response.json();
  },

  async getIntrusions(limit: number = 50): Promise<Event[]> {
    const response = await fetch(`${API_BASE_URL}/intrusions?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to fetch intrusions');
    return response.json();
  },

  async getRecognized(limit: number = 50): Promise<Event[]> {
    const response = await fetch(`${API_BASE_URL}/recognized?limit=${limit}`);
    if (!response.ok) throw new Error('Failed to fetch recognized events');
    return response.json();
  },

  async triggerManualCapture(cameraId: number = 0): Promise<{ status: string; message: string }> {
    // We add ?camera_id= to the URL so FastAPI knows which one you want
    const response = await fetch(`${API_BASE_URL}/pi/capture?camera_id=${cameraId}`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error(`Failed to trigger Pi capture for Camera ${cameraId}`);
    return response.json();
  },

  async subscribePush(subscription: any): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE_URL}/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(subscription)
    });
    if (!response.ok) throw new Error('Failed to subscribe');
    return response.json();
  },

  async getPiStatus(): Promise<{ online: boolean; connections: number }> {
    const response = await fetch(`${API_BASE_URL}/pi/status`);
    if (!response.ok) throw new Error('Failed to fetch Pi status');
    return response.json();
  }
};