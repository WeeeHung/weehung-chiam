/**
 * Atlantis Bar component - voice assistant interface.
 * Supports two modes:
 * - Outside EventDialog: Device STT/TTS with push-to-talk for map navigation commands
 * - Inside EventDialog: Syncs with Gemini Live API state
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { geocodeLocation } from "../utils/geocoding";
import { Viewport } from "../types/events";

interface AtlantisBarProps {
  // Mode: true when EventDialog is open
  isInDialog: boolean;
  
  // EventDialog state (when isInDialog is true)
  dialogState?: {
    connectionStatus: "idle" | "connecting" | "connected" | "error";
    isPlaying: boolean;
    isExplaining?: boolean;
  };
  
  // Navigation callbacks
  onNavigateToLocation?: (viewport: Viewport) => void;
  onLanguageChange?: (language: string) => void;
  onDateChange?: (date: string) => void;
  onManualFetch?: () => void;
  
  // Current state
  currentLanguage: string;
}

// Language code mapping
const LANGUAGE_MAP: Record<string, string> = {
  "english": "en",
  "chinese": "zh",
  "japanese": "ja",
  "spanish": "es",
  "french": "fr",
  "german": "de",
  "korean": "ko",
  "portuguese": "pt",
  "russian": "ru",
  "arabic": "ar",
  "hindi": "hi",
  // Add more as needed
};

/**
 * Parse voice command to extract location, language, and date.
 * Returns parsed entities or null if no valid command detected.
 */
function parseVoiceCommand(text: string): {
  location?: string;
  language?: string;
  date?: string;
} | null {
  const lowerText = text.toLowerCase().trim();
  
  // Skip if too short or doesn't contain relevant keywords
  if (lowerText.length < 3) return null;
  
  const result: { location?: string; language?: string; date?: string } = {};
  
  // Extract language (e.g., "in chinese", "in japanese")
  const languageMatch = lowerText.match(/\bin\s+(\w+)/);
  if (languageMatch) {
    const langName = languageMatch[1];
    if (LANGUAGE_MAP[langName]) {
      result.language = LANGUAGE_MAP[langName];
    }
  }
  
  // Extract date patterns (e.g., "today", "yesterday", specific dates)
  if (lowerText.includes("today")) {
    const today = new Date();
    result.date = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  } else if (lowerText.includes("yesterday")) {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    result.date = `${yesterday.getFullYear()}-${String(yesterday.getMonth() + 1).padStart(2, "0")}-${String(yesterday.getDate()).padStart(2, "0")}`;
  }
  
  // Extract location - look for patterns like "check out {location}", "go to {location}", or just "{location}"
  let locationMatch: RegExpMatchArray | null = null;
  
  // Pattern 1: "check out {location}" or "let's check out {location}"
  locationMatch = lowerText.match(/(?:let'?s\s+)?check\s+out\s+(.+?)(?:\s+in\s+\w+)?(?:\s+today)?$/i);
  if (!locationMatch) {
    // Pattern 2: "go to {location}"
    locationMatch = lowerText.match(/go\s+to\s+(.+?)(?:\s+in\s+\w+)?(?:\s+today)?$/i);
  }
  if (!locationMatch) {
    // Pattern 3: "{location} in {language}"
    locationMatch = lowerText.match(/(.+?)\s+in\s+(\w+)/);
    if (locationMatch) {
      const langName = locationMatch[2];
      if (LANGUAGE_MAP[langName]) {
        result.language = LANGUAGE_MAP[langName];
      }
      locationMatch = [null as unknown as string, locationMatch[1]]; // Extract location part
    }
  }
  if (!locationMatch) {
    // Pattern 4: Just a location name (simple case - take first substantial word sequence)
    const words = lowerText.split(/\s+/).filter(w => 
      w.length > 2 && 
      !["in", "out", "to", "go", "check", "lets", "let's", "today", "yesterday"].includes(w)
    );
    if (words.length > 0) {
      result.location = words.join(" ");
    }
  } else if (locationMatch[1]) {
    // Extract location from matched pattern
    let location = locationMatch[1].trim();
    // Remove language and date keywords if present
    location = location.replace(/\s+in\s+\w+$/i, "").replace(/\s+today$/i, "").trim();
    if (location) {
      result.location = location;
    }
  }
  
  // Return null if no useful information extracted
  if (!result.location && !result.language && !result.date) {
    return null;
  }
  
  return result;
}

/**
 * Create a viewport centered on a lat/lng coordinate with a reasonable zoom level.
 */
function createViewportFromLocation(lat: number, lng: number, zoom: number = 10): Viewport {
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

export function AtlantisBar({
  isInDialog,
  dialogState,
  onNavigateToLocation,
  onLanguageChange,
  onDateChange,
  onManualFetch,
  currentLanguage,
}: AtlantisBarProps) {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [recognition, setRecognition] = useState<any>(null);
  const recognitionRef = useRef<any>(null);
  const isSpacePressedRef = useRef(false);

  // Initialize Speech Recognition API
  useEffect(() => {
    if (isInDialog) {
      // Don't initialize speech recognition when in dialog (using Gemini Live API instead)
      return;
    }

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
      console.warn("Speech Recognition API not supported in this browser");
      return;
    }

    const recognitionInstance = new SpeechRecognition();
    recognitionInstance.continuous = false;
    recognitionInstance.interimResults = false;
    recognitionInstance.lang = currentLanguage === "zh" ? "zh-CN" : currentLanguage;

    recognitionInstance.onstart = () => {
      console.log("Speech recognition started");
      setIsListening(true);
    };

    recognitionInstance.onresult = async (event: any) => {
      const transcript = event.results[0][0].transcript;
      console.log("Speech recognition result:", transcript);
      
      setIsListening(false);
      setIsProcessing(true);

      // Parse command
      const parsed = parseVoiceCommand(transcript);
      
      if (!parsed) {
        console.log("No valid command detected in:", transcript);
        setIsProcessing(false);
        return;
      }

      console.log("Parsed command:", parsed);

      // Handle language change
      if (parsed.language && onLanguageChange) {
        onLanguageChange(parsed.language);
      }

      // Handle date change
      if (parsed.date && onDateChange) {
        onDateChange(parsed.date);
      }

      // Handle location navigation
      if (parsed.location && onNavigateToLocation) {
        try {
          const geocoded = await geocodeLocation(parsed.location);
          if (geocoded) {
            const viewport = createViewportFromLocation(geocoded.lat, geocoded.lng, 11);
            onNavigateToLocation(viewport);
          } else {
            console.error(`Could not geocode location: ${parsed.location}`);
          }
        } catch (error) {
          console.error("Error geocoding location:", error);
        }
      }

      setIsProcessing(false);
    };

    recognitionInstance.onerror = (event: any) => {
      console.error("Speech recognition error:", event.error);
      setIsListening(false);
      setIsProcessing(false);
    };

    recognitionInstance.onend = () => {
      setIsListening(false);
      
      // Restart if spacebar is still pressed
      if (isSpacePressedRef.current && !isInDialog) {
        try {
          recognitionInstance.start();
        } catch (error) {
          // Ignore errors (might already be started)
        }
      }
    };

    setRecognition(recognitionInstance);
    recognitionRef.current = recognitionInstance;

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          // Ignore
        }
      }
    };
  }, [isInDialog, currentLanguage]);

  // Handle spacebar push-to-talk
  useEffect(() => {
    if (isInDialog || !recognition) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code === "Space" && !event.repeat) {
        event.preventDefault();
        isSpacePressedRef.current = true;
        
        if (!isListening && !isProcessing) {
          try {
            recognition.start();
          } catch (error) {
            // Already started or error
            console.error("Error starting speech recognition:", error);
          }
        }
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") {
        event.preventDefault();
        isSpacePressedRef.current = false;
        
        if (recognitionRef.current && isListening) {
          try {
            recognitionRef.current.stop();
          } catch (error) {
            // Ignore
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [isListening, isProcessing, isInDialog, recognition]);

  // Determine display state
  let displayText = "Atlantis";
  let isGlowing = false;

  if (isInDialog && dialogState) {
    // Dialog mode: sync with Gemini Live API state
    if (dialogState.connectionStatus === "idle") {
      displayText = dialogState.isExplaining ? "Loading article..." : "Atlantis";
    } else if (dialogState.connectionStatus === "connecting") {
      displayText = "Connecting...";
    } else if (dialogState.connectionStatus === "connected") {
      displayText = dialogState.isPlaying ? "Atlantis is speaking..." : "Atlantis is listening...";
      isGlowing = dialogState.isPlaying;
    } else if (dialogState.connectionStatus === "error") {
      displayText = "Connection Error";
    }
  } else {
    // Outside dialog mode: device STT/TTS
    if (isProcessing) {
      displayText = "Processing command...";
    } else if (isListening) {
      displayText = "Listening... (release space to finish)";
      isGlowing = true;
    } else {
      displayText = "Press space to talk";
    }
  }

  const handleManualFetch = useCallback(() => {
    if (onManualFetch) {
      onManualFetch();
    }
  }, [onManualFetch]);

  return (
    <div className={`atlantis-bar ${isGlowing ? 'glowing' : ''}`} onClick={(e) => e.stopPropagation()}>
      <div 
        className="atlantis-button"
        style={{ cursor: 'default', pointerEvents: 'none', textAlign: 'center', flex: 1 }}
      >
        {displayText}
      </div>
      {!isInDialog && (
        <button
          className="record-button"
          onClick={handleManualFetch}
          title="Fetch pins for current view"
          style={{ marginLeft: '8px' }}
        >
          🔍
        </button>
      )}
    </div>
  );
}
