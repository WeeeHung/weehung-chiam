/**
 * Atlantis Bar component - voice assistant interface.
 * Supports two modes:
 * - Outside EventDialog: Device STT/TTS with push-to-talk for map navigation commands
 * - Inside EventDialog: Syncs with Gemini Live API state
 */

import { useState, useEffect, useRef, useCallback } from "react";
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

/**
 * Map ISO 639-1 language codes to BCP-47 locale codes for Web Speech API.
 * The Web Speech API requires BCP-47 codes (e.g., "en-US", "zh-CN") for proper recognition.
 */
function getSpeechRecognitionLanguage(isoCode: string): string {
  // Get browser's preferred language as fallback
  const browserLang = navigator.language || (navigator as any).userLanguage || "en-US";
  
  // Map ISO 639-1 codes to BCP-47 codes
  const speechLangMap: Record<string, string> = {
    "en": "en-US",
    "zh": "zh-CN",
    "ja": "ja-JP",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "ko": "ko-KR",
    "pt": "pt-BR",
    "ru": "ru-RU",
    "ar": "ar-SA",
    "hi": "hi-IN",
  };
  
  // Use mapped code if available, otherwise try browser language
  const mapped = speechLangMap[isoCode];
  if (mapped) {
    return mapped;
  }
  
  // Fallback: if browser language matches the base language, use it
  if (browserLang.startsWith(isoCode + "-")) {
    return browserLang;
  }
  
  // Final fallback: use browser language or default to en-US
  return browserLang || "en-US";
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
    
    // Use proper BCP-47 language code for better recognition accuracy
    const speechLang = getSpeechRecognitionLanguage(currentLanguage);
    recognitionInstance.lang = speechLang;
    console.log(`Speech recognition language set to: ${speechLang} (from currentLanguage: ${currentLanguage})`);

    recognitionInstance.onstart = () => {
      console.log("Speech recognition started");
      setIsListening(true);
    };

    recognitionInstance.onresult = async (event: any) => {
      const transcript = event.results[0][0].transcript;
      console.log("Speech recognition result:", transcript);
      
      setIsListening(false);
      setIsProcessing(true);

      try {
        // Call backend API to parse command using Gemini
        const response = await fetch("/api/events/parse-command", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ text: transcript }),
        });

        if (!response.ok) {
          throw new Error(`API error: ${response.statusText}`);
        }

        const parsed = await response.json();
        console.log("Parsed command:", parsed);

        // Handle location navigation (with lat/lng from geocoding)
        if (parsed.location && parsed.location.lat && parsed.location.lng && onNavigateToLocation) {
          const viewport = createViewportFromLocation(parsed.location.lat, parsed.location.lng, 11);
          onNavigateToLocation(viewport);
        }

        // Handle language change
        if (parsed.language && onLanguageChange) {
          onLanguageChange(parsed.language);
        }

        // Handle date change
        if (parsed.date && onDateChange) {
          onDateChange(parsed.date);
        }

        // Log if nothing was extracted
        if (!parsed.location && !parsed.language && !parsed.date) {
          console.log("No valid entities extracted from:", transcript);
        }

      } catch (error) {
        console.error("Error parsing command:", error);
        // Fallback: try to extract just location name for geocoding
        // (simple fallback if API fails)
        const words = transcript.toLowerCase().trim().split(/\s+/).filter((w: string): boolean => 
          w.length > 2 && 
          !["want", "yesterday", "today", "news", "for", "to", "the", "a", "an", "in", "at", "on"].includes(w)
        );
        if (words.length > 0 && words.length <= 3 && onNavigateToLocation) {
          // Try basic geocoding as fallback
          try {
            const { geocodeLocation } = await import("../utils/geocoding");
            const locationName = words.slice(0, 3).join(" ");
            const geocoded = await geocodeLocation(locationName);
            if (geocoded) {
              const viewport = createViewportFromLocation(geocoded.lat, geocoded.lng, 11);
              onNavigateToLocation(viewport);
            }
          } catch (fallbackError) {
            console.error("Fallback geocoding also failed:", fallbackError);
          }
        }
      } finally {
        setIsProcessing(false);
      }
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
      displayText = "Listening... (release `Spacebar` to finish)";
      isGlowing = true;
    } else {
      displayText = "Press `Spacebar` to talk";
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
