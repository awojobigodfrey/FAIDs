import { useState, useEffect } from 'react';
import { ShieldAlert, UserCheck, Camera, Activity } from 'lucide-react';
import { StatCard } from './components/StatCard';
import { EventCard } from './components/EventCard';
import { PushNotification } from './components/PushNotification';
import { api } from './services/api';
import type { Event, Stats } from './types';

function App() {
  const [stats, setStats] = useState<Stats>({ total_intrusions: 0, total_recognized: 0 });
  const [intrusions, setIntrusions] = useState<Event[]>([]);
  const [recognized, setRecognized] = useState<Event[]>([]);
  const [activeTab, setActiveTab] = useState<'intrusions' | 'recognized'>('intrusions');
  const [loading, setLoading] = useState(true);
  const [isCapturing, setIsCapturing] = useState(false);
  const [isOnline, setIsOnline] = useState(false);

  const fetchData = async () => {
    try {
      const [statsData, intrusionsData, recognizedData, statusData] = await Promise.all([
        api.getStats(),
        api.getIntrusions(50),
        api.getRecognized(50),
        api.getPiStatus(),
      ]);

      setStats(statsData);
      setIntrusions(intrusionsData);
      setRecognized(recognizedData);
      setIsOnline(statusData.online);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleManualCapture = async (cameraId: number) => {
    setIsCapturing(true);
    try {
      await api.triggerManualCapture(cameraId);
      // Give the Pi ~3 seconds to take the photo and upload it
      setTimeout(async () => {
        await fetchData();
        setIsCapturing(false);
      }, 3000);
    } catch (error) {
      console.error('Error triggering capture:', error);
      setIsCapturing(false);
    }
  };

  if (loading && !stats.total_intrusions && !stats.total_recognized) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center">
        <div className="text-center">
          <Activity className="animate-spin mx-auto mb-4" size={48} color="#3b82f6" />
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  const displayEvents = activeTab === 'intrusions' ? intrusions : recognized;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">
                Agricultural Intrusion Detection
              </h1>
              <div className="flex items-center gap-3">
                <p className="text-gray-600">Raspberry Pi Edge Monitoring Dashboard</p>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1 ${isOnline ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                  <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></span>
                  {isOnline ? 'System Online' : 'System Offline'}
                </span>
              </div>
            </div>
            <div className="flex flex-wrap gap-3 items-center">
              <PushNotification />
              <button
                onClick={() => handleManualCapture(0)}
                disabled={isCapturing}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all ${
                  isCapturing
                    ? 'bg-blue-400 cursor-not-allowed text-white'
                    : 'bg-blue-600 hover:bg-blue-700 text-white'
                }`}
              >
                <Camera size={20} className={isCapturing ? 'animate-pulse' : ''} />
                {isCapturing ? 'Capturing...' : 'Capture (Cam 1)'}
              </button>
              
              <button
                onClick={() => handleManualCapture(2)}
                disabled={isCapturing}
                className={`flex items-center gap-2 px-6 py-3 rounded-lg font-semibold transition-all ${
                  isCapturing
                    ? 'bg-indigo-400 cursor-not-allowed text-white'
                    : 'bg-indigo-600 hover:bg-indigo-700 text-white'
                }`}
              >
                <Camera size={20} className={isCapturing ? 'animate-pulse' : ''} />
                {isCapturing ? 'Capturing...' : 'Capture (Cam 2)'}
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <StatCard
            title="Total Intrusions"
            value={stats.total_intrusions}
            icon={ShieldAlert}
            color="#ef4444"
          />
          <StatCard
            title="Recognized Visits"
            value={stats.total_recognized}
            icon={UserCheck}
            color="#10b981"
          />
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex gap-4 mb-6 border-b">
            <button
              onClick={() => setActiveTab('intrusions')}
              className={`pb-3 px-4 font-semibold transition-all ${
                activeTab === 'intrusions'
                  ? 'border-b-2 border-red-500 text-red-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Intrusions ({intrusions.length})
            </button>
            <button
              onClick={() => setActiveTab('recognized')}
              className={`pb-3 px-4 font-semibold transition-all ${
                activeTab === 'recognized'
                  ? 'border-b-2 border-green-500 text-green-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              Recognized ({recognized.length})
            </button>
          </div>

          {displayEvents.length === 0 ? (
            <div className="text-center py-12">
              <Activity size={48} className="mx-auto mb-4 text-gray-400" />
              <p className="text-gray-600">
                No {activeTab === 'intrusions' ? 'intrusions' : 'recognized visits'} detected yet
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {displayEvents.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;