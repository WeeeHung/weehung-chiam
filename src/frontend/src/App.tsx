/**
 * Main App component for Atlantis.
 */

import { useState, useCallback, useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./components/AppShell";
import { WorldMap } from "./components/WorldMap";
import { EventDialog } from "./components/EventDialog";
import { AtlantisBar } from "./components/AtlantisBar";
import { WelcomeModal } from "./components/WelcomeModal";
import { usePins } from "./hooks/useEvents";
import { useLoadingMessage } from "./hooks/useLoadingMessage";
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
  const [welcomeCompleted, setWelcomeCompleted] = useState(false);
  // Default to last 7 days
  const [startDate, setStartDate] = useState(() => {
    const today = new Date();
    const sevenDaysAgo = new Date(today);
    sevenDaysAgo.setDate(today.getDate() - 6); // 7 days inclusive (today + 6 days ago)
    return `${sevenDaysAgo.getFullYear()}-${String(sevenDaysAgo.getMonth() + 1).padStart(2, "0")}-${String(sevenDaysAgo.getDate()).padStart(2, "0")}`;
  });
  const [endDate, setEndDate] = useState(() => {
    const today = new Date();
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  });
  const [language, setLanguage] = useState("en");
  const [mapStyle, setMapStyle] = useState<MapStyle>("mapbox://styles/mapbox/outdoors-v12");
  const [viewport, setViewport] = useState<Viewport>(defaultViewport);
  const [selectedPin, setSelectedPin] = useState<Pin | null>(null);
  const [relatedPinIds, setRelatedPinIds] = useState<string[]>([]);
  const [locationInitialized, setLocationInitialized] = useState(false);
  const [homeLocation, setHomeLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [canFetchEvents, setCanFetchEvents] = useState(false);
  const [eventDialogState, setEventDialogState] = useState<{
    connectionStatus: "idle" | "connecting" | "connected" | "error";
    isPlaying: boolean;
    isExplaining?: boolean;
  } | null>(null);

  // Wait 2 seconds before allowing event fetching (to allow map animation to complete)
  useEffect(() => {
    const timer = setTimeout(() => {
      setCanFetchEvents(true);
    }, 4500);

    return () => clearTimeout(timer);
  }, []);

  // Request user location on mount
  useEffect(() => {
    if (locationInitialized || !navigator.geolocation) {
      // Geolocation not supported, use NYC as fallback
      if (!locationInitialized) {
        setHomeLocation({ lat: NYC_LAT, lng: NYC_LNG });
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
        // Store user's location as home location
        setHomeLocation({ lat: latitude, lng: longitude });
        setViewport(createViewportFromLocation(latitude, longitude, 11));
        setLocationInitialized(true);
      },
      (error) => {
        // Error or permission denied: use NYC as fallback
        console.log("Geolocation error:", error.message);
        console.log("Falling back to NYC location:", { lat: NYC_LAT, lng: NYC_LNG });
        setHomeLocation({ lat: NYC_LAT, lng: NYC_LNG });
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
  const { data: pinsData, isLoading: isLoadingPins, manualRefetch } = usePins(
    startDate,
    endDate,
    viewport,
    language,
    8,
    canFetchEvents
  );

  // Streaming loading message
  const loadingMessage = useLoadingMessage({ enabled: isLoadingPins });

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

  // Reset accumulated pins when date or language changes
  useEffect(() => {
    setAccumulatedPins([]);
    // Also close any open dialog when resetting
    setSelectedPin(null);
    setRelatedPinIds([]);
  }, [startDate, endDate, language]);

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

  // Handle navigation to location (from voice commands)
  const handleNavigateToLocation = useCallback((newViewport: Viewport) => {
    setViewport(newViewport);
    // Trigger pins fetch with new viewport
    if (manualRefetch) {
      manualRefetch(newViewport, undefined, undefined, undefined);
    }
  }, [manualRefetch]);

  // Handle manual fetch button click
  const handleManualFetch = useCallback(() => {
    if (manualRefetch) {
      manualRefetch(undefined, undefined, undefined, undefined);
    }
  }, [manualRefetch]);

  // Handle language change from voice command
  const handleLanguageChangeFromVoice = useCallback((newLanguage: string) => {
    setLanguage(newLanguage);
    // Trigger pins fetch with new language
    if (manualRefetch) {
      manualRefetch(undefined, undefined, undefined, newLanguage);
    }
  }, [manualRefetch]);

  // Handle date change from voice command
  const handleDateChangeFromVoice = useCallback((newStartDate: string, newEndDate: string) => {
    setStartDate(newStartDate);
    setEndDate(newEndDate);
    // Trigger pins fetch with new date
    if (manualRefetch) {
      manualRefetch(undefined, newStartDate, newEndDate, undefined);
    }
  }, [manualRefetch]);

  // Handle home click - navigate to user's initial location (or NYC fallback)
  const handleHomeClick = useCallback(() => {
    const lat = homeLocation ? homeLocation.lat : NYC_LAT;
    const lng = homeLocation ? homeLocation.lng : NYC_LNG;
    const homeViewport = createViewportFromLocation(lat, lng, 11);
    setViewport(homeViewport);
    if (manualRefetch) {
      manualRefetch(homeViewport, undefined, undefined, undefined);
    }
  }, [manualRefetch, homeLocation]);

  // Handle random event click - fetch random historic event and navigate
  const handleRandomClick = useCallback(async () => {
    try {
      const response = await fetch("/api/events/random-event", {
        method: "GET",
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const randomEvent = await response.json();
      console.log("Random event:", randomEvent);

      // Update date range if provided
      if (randomEvent.start_date && randomEvent.end_date) {
        setStartDate(randomEvent.start_date);
        setEndDate(randomEvent.end_date);
      }

      // Navigate to location if provided
      if (randomEvent.location && randomEvent.location.lat && randomEvent.location.lng) {
        const viewport = createViewportFromLocation(
          randomEvent.location.lat,
          randomEvent.location.lng,
          11
        );
        setViewport(viewport);
        
        // Trigger pins fetch with new location and date
        if (manualRefetch) {
          manualRefetch(
            viewport,
            randomEvent.start_date,
            randomEvent.end_date,
            randomEvent.language || undefined
          );
        }
      } else if (randomEvent.start_date && randomEvent.end_date) {
        // If only date was provided, just refetch with new date
        if (manualRefetch) {
          manualRefetch(undefined, randomEvent.start_date, randomEvent.end_date, undefined);
        }
      }
    } catch (error) {
      console.error("Error fetching random event:", error);
    }
  }, [manualRefetch]);

  // Mapbox token from environment
  const mapboxToken = import.meta.env.VITE_MAPBOX_TOKEN;
  const hasMapboxToken = mapboxToken && mapboxToken !== "YOUR_MAPBOX_TOKEN" && mapboxToken.trim() !== "";

  // Show welcome modal first
  if (!welcomeCompleted) {
    return (
      <div className="app">
        <WelcomeModal onComplete={() => setWelcomeCompleted(true)} />
      </div>
    );
  }

  return (
    <div className="app">
      <AppShell
        startDate={startDate}
        endDate={endDate}
        language={language}
        mapStyle={mapStyle}
        onDateChange={(start, end) => {
          setStartDate(start);
          setEndDate(end);
        }}
        onLanguageChange={setLanguage}
        onMapStyleChange={setMapStyle}
      />
      <div className="app-content">
        <div className="map-container">
          {isLoadingPins && <div className="loading-overlay">{loadingMessage}</div>}
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
          allPins={pins}
          language={language}
          onClose={() => {
            setSelectedPin(null);
            setRelatedPinIds([]);
            setEventDialogState(null);
          }}
          onPinChange={(newPin) => {
            setSelectedPin(newPin);
            if (newPin.related_event_ids && newPin.related_event_ids.length > 0) {
              setRelatedPinIds(newPin.related_event_ids);
            } else {
              setRelatedPinIds([]);
            }
          }}
          onStateChange={setEventDialogState}
        />
      )}
      
      {/* Atlantis Bar - always visible */}
      <AtlantisBar
        isInDialog={!!selectedPin}
        dialogState={eventDialogState || undefined}
        onNavigateToLocation={handleNavigateToLocation}
        onLanguageChange={handleLanguageChangeFromVoice}
        onDateChange={handleDateChangeFromVoice}
        onManualFetch={handleManualFetch}
        onHomeClick={handleHomeClick}
        onRandomClick={handleRandomClick}
        currentLanguage={language}
      />
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

