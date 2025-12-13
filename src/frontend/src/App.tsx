/**
 * Main App component for Atlantis.
 */

import { useState, useCallback, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./components/AppShell";
import { WorldMap } from "./components/WorldMap";
import { EventDialog } from "./components/EventDialog";
import { usePins } from "./hooks/useEvents";
import { Pin, Viewport } from "./types/events";
import { MapStyle } from "./components/MapStylePicker";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// New York City coordinates (fallback location)
const NYC_LAT = 40.7128;
const NYC_LNG = -74.0060;

// Default viewport (world view)
const defaultViewport: Viewport = {
  bbox: {
    west: -180,
    south: -90,
    east: 180,
    north: 90,
  },
  zoom: 2,
};

/**
 * Create a viewport centered on a lat/lng coordinate with a reasonable zoom level
 */
function createViewportFromLocation(lat: number, lng: number, zoom: number = 10): Viewport {
  // Create a bounding box around the center point
  // At zoom 10, roughly 0.2 degrees covers a city-sized area
  const bboxSize = 0.2 / Math.pow(2, 12 - zoom);
  
  return {
    bbox: {
      west: lng - bboxSize,
      south: lat - bboxSize,
      east: lng + bboxSize,
      north: lat + bboxSize,
    },
    zoom,
  };
}

function AppContent() {
  const [date, setDate] = useState(() => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  });
  const [language, setLanguage] = useState("en");
  const [mapStyle, setMapStyle] = useState<MapStyle>("mapbox://styles/mapbox/outdoors-v12");
  const [viewport, setViewport] = useState<Viewport>(defaultViewport);
  const [selectedPin, setSelectedPin] = useState<Pin | null>(null);
  const [relatedPinIds, setRelatedPinIds] = useState<string[]>([]);
  const [locationInitialized, setLocationInitialized] = useState(false);
  const [canFetchEvents, setCanFetchEvents] = useState(false);

  // Wait 2 seconds before allowing event fetching (to allow map animation to complete)
  useEffect(() => {
    const timer = setTimeout(() => {
      setCanFetchEvents(true);
    }, 2000);

    return () => clearTimeout(timer);
  }, []);

  // Request user location on mount
  useEffect(() => {
    if (locationInitialized || !navigator.geolocation) {
      // Geolocation not supported, use NYC as fallback
      if (!locationInitialized) {
        setViewport(createViewportFromLocation(NYC_LAT, NYC_LNG, 11));
        setLocationInitialized(true);
      }
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        // Success: use user's location
        const { latitude, longitude } = position.coords;
        console.log("User location retrieved:", {
          latitude,
          longitude,
          accuracy: position.coords.accuracy,
          timestamp: new Date(position.timestamp).toISOString(),
        });
        setViewport(createViewportFromLocation(latitude, longitude, 11));
        setLocationInitialized(true);
      },
      (error) => {
        // Error or permission denied: use NYC as fallback
        console.log("Geolocation error:", error.message);
        console.log("Falling back to NYC location:", { lat: NYC_LAT, lng: NYC_LNG });
        setViewport(createViewportFromLocation(NYC_LAT, NYC_LNG, 11));
        setLocationInitialized(true);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  }, [locationInitialized]);

  // Accumulate pins across all fetches (don't reset on new queries)
  const [accumulatedPins, setAccumulatedPins] = useState<Pin[]>([]);

  // Fetch pins (viewport is already debounced in WorldMap component)
  // Wait for initial delay to complete before fetching
  const { data: pinsData, isLoading: isLoadingPins } = usePins(
    date,
    viewport,
    language,
    8,
    canFetchEvents
  );

  // Merge new pins with accumulated pins (deduplicate by event_id)
  useEffect(() => {
    if (pinsData?.pins) {
      setAccumulatedPins((prev) => {
        const existingIds = new Set(prev.map((p) => p.event_id));
        const newPins = pinsData.pins.filter((p) => !existingIds.has(p.event_id));
        return [...prev, ...newPins];
      });
    }
  }, [pinsData?.pins]);

  // Reset accumulated pins when date changes
  useEffect(() => {
    setAccumulatedPins([]);
  }, [date]);

  const pins = accumulatedPins;

  // Handle pin click
  const handlePinClick = useCallback((pin: Pin) => {
    setSelectedPin(pin);
    if (pin.related_event_ids && pin.related_event_ids.length > 0) {
      setRelatedPinIds(pin.related_event_ids);
    } else {
      setRelatedPinIds([]);
    }
  }, []);

  // Mapbox token from environment
  const mapboxToken = import.meta.env.VITE_MAPBOX_TOKEN;
  const hasMapboxToken = mapboxToken && mapboxToken !== "YOUR_MAPBOX_TOKEN" && mapboxToken.trim() !== "";

  return (
    <div className="app">
      <AppShell
        date={date}
        language={language}
        mapStyle={mapStyle}
        onDateChange={setDate}
        onLanguageChange={setLanguage}
        onMapStyleChange={setMapStyle}
      />
      <div className="app-content">
        <div className="map-container">
          {isLoadingPins && <div className="loading-overlay">Loading events...</div>}
          {!hasMapboxToken ? (
            <div className="map-error-overlay">
              <div className="map-error-message">
                <h3>Mapbox Token Required</h3>
                <p>Please set your Mapbox access token in the environment variables.</p>
                <ol>
                  <li>Create a <code>.env</code> file in the <code>src/frontend/</code> directory</li>
                  <li>Add: <code>VITE_MAPBOX_TOKEN=your_token_here</code></li>
                  <li>Get your token from: <a href="https://account.mapbox.com/access-tokens/" target="_blank" rel="noopener noreferrer">Mapbox Access Tokens</a></li>
                  <li>Restart the development server</li>
                </ol>
                <p className="map-error-note">The map will not render without a valid token.</p>
              </div>
            </div>
          ) : (
            <WorldMap
              pins={pins}
              viewport={viewport}
              onViewportChange={setViewport}
              onPinClick={handlePinClick}
              selectedPinId={selectedPin?.event_id}
              relatedPinIds={relatedPinIds}
              mapboxToken={mapboxToken}
              mapStyle={mapStyle}
            />
          )}
        </div>
      </div>
      {selectedPin && (
        <EventDialog
          pin={selectedPin}
          language={language}
          onClose={() => {
            setSelectedPin(null);
            setRelatedPinIds([]);
          }}
        />
      )}
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

