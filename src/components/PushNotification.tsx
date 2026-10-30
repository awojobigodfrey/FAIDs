import React, { useState, useEffect } from 'react';
import { Bell, BellOff } from 'lucide-react';
import { api } from '../services/api';

// Replace or set via .env
const PUBLIC_VAPID_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY || 'BJ8wIrcS9nWFUGDUXfCp7wE2H4IALuUy4Xhj-A8bwvVpcGcVKM9O1GJoR_4BhttOWrNaWH-5ccqcEbDrxhE-M_Q';

function urlBase64ToUint8Array(base64String: string) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function PushNotification() {
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [isSupported, setIsSupported] = useState(false);

  useEffect(() => {
    if ('serviceWorker' in navigator && 'PushManager' in window) {
      setIsSupported(true);
      
      navigator.serviceWorker.register('/service-worker.js')
        .then(registration => {
          return registration.pushManager.getSubscription();
        })
        .then(subscription => {
          setIsSubscribed(subscription !== null);
        })
        .catch(err => console.error("Service Worker error:", err));
    }
  }, []);

  const subscribe = async () => {
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        alert('Notification permission denied.');
        return;
      }

      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(PUBLIC_VAPID_KEY)
      });
      
      const subJSON = subscription.toJSON();
      await api.subscribePush({
        endpoint: subJSON.endpoint,
        p256dh: subJSON.keys?.p256dh,
        auth: subJSON.keys?.auth
      });
      
      setIsSubscribed(true);
      alert('Successfully subscribed to push notifications!');
    } catch (err) {
      console.error('Failed to subscribe:', err);
      alert('Failed to subscribe. Check console for details.');
    }
  };

  if (!isSupported) return null;

  return (
    <button
      onClick={subscribe}
      disabled={isSubscribed}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-all ${
        isSubscribed
          ? 'bg-green-100 text-green-700 cursor-not-allowed'
          : 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
      }`}
    >
      {isSubscribed ? <Bell size={20} /> : <BellOff size={20} />}
      <span className="hidden sm:inline">{isSubscribed ? 'Notifications Enabled' : 'Enable Notifications'}</span>
    </button>
  );
}
