import { Event } from '../types';
import { formatDistanceToNow } from '../utils/date';

interface EventCardProps {
  event: Event;
}

export function EventCard({ event }: EventCardProps) {
  const reasonLabels: Record<string, string> = {
    mask_detected: 'Face Mask Detected',
    unknown_face: 'Unknown Face',
    recognized_face: 'Recognized Person',
  };

  const getBadgeColor = () => {
    if (event.event_type === 'intrusion') {
      return 'bg-red-100 text-red-800 border-red-200';
    }
    return 'bg-green-100 text-green-800 border-green-200';
  };

  return (
    <div className="bg-white rounded-lg shadow-md overflow-hidden hover:shadow-lg transition-shadow">
      <div className="aspect-video bg-gray-200 relative">
        <img
          src={event.image_url}
          alt={event.reason}
          className="w-full h-full object-cover"
          onError={(e) => {
            e.currentTarget.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300"%3E%3Crect fill="%23ddd" width="400" height="300"/%3E%3Ctext fill="%23999" x="50%25" y="50%25" text-anchor="middle" dy=".3em"%3EImage Not Available%3C/text%3E%3C/svg%3E';
          }}
        />
        {event.confidence && (
          <div className="absolute top-2 right-2 bg-black bg-opacity-70 text-white text-xs px-2 py-1 rounded">
            {(event.confidence * 100).toFixed(1)}%
          </div>
        )}
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${getBadgeColor()}`}>
            {reasonLabels[event.reason] || event.reason}
          </span>
        </div>
        {event.person_name && (
          <p className="text-lg font-semibold text-gray-900 mb-1">{event.person_name}</p>
        )}
        <p className="text-sm text-gray-600">
          {formatDistanceToNow(event.timestamp)}
        </p>
      </div>
    </div>
  );
}
