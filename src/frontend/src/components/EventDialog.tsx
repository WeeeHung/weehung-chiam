/**
 * Event dialog component for displaying event details and Q&A.
 */

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import { Pin } from "../types/events";
import { useSentenceStream } from "../hooks/useSentenceStream";
import { useLiveAPI } from "../hooks/useLiveAPI";
import { AudioRecorder } from "../lib/audio-recorder";

interface EventDialogProps {
  pin: Pin | null;
  allPins: Pin[];
  language: string;
  onClose: () => void;
  onPinChange?: (pin: Pin) => void;
  onStateChange?: (state: {
    connectionStatus: "idle" | "connecting" | "connected" | "error";
    isPlaying: boolean;
    isExplaining?: boolean;
  }) => void;
}

type ConnectionStatus = "idle" | "connecting" | "connected" | "error";

export function EventDialog({ pin, allPins, language, onClose, onPinChange, onStateChange }: EventDialogProps) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("idle");
  const hasSentInitialIntroRef = useRef(false);
  const shouldAutoStartRef = useRef(false);

  // Stream explanation sentence by sentence
  const explanationUrl = pin
    ? `/api/events/${pin.event_id}/explain/stream?language=${language}`
    : "";

  const { displayedText: explanation, isStreaming: isExplaining } = useSentenceStream(
    explanationUrl,
    {
      onDone: () => {
        // Auto-start Live API when article streaming completes
        if (pin && shouldAutoStartRef.current) {
          console.log("[AUTO-START] Article streaming completed, starting Live API...");
          handleStartLiveAPI();
        }
      }
    }
  );

  // Get API key from environment
  const apiKey = import.meta.env.VITE_GEMINI_API_KEY || "";

  // Build system instruction from event information
  const systemInstruction = pin
    ? `You are Atlantis, a news reporter AI assistant with access to web search, reporting on historical events to a single person.

Event Information:
- Title: ${pin.title}
- Date: ${pin.date}
- Location: ${pin.location_label}
- Category: ${pin.category}
- Significance Score: ${pin.significance_score}
${explanation ? `- Event Report: ${explanation.substring(0, 500)}...` : ''}

When you first start, introduce yourself as a news reporter and give a brief, engaging news-style report about this event. After that initial introduction, switch to answering questions in a conversational Q&A format.

You have access to web search capabilities. Use web search to find current, accurate information about this event and related topics. Provide detailed, well-researched answers based on web search results when relevant.

Respond in ${language}. Be conversational and helpful. Keep responses concise for voice output.`
    : "You are a helpful assistant.";

  // Initialize Live API hook
  const {
    client,
    connected,
    connect,
    disconnect,
    isModelTurn,
    setConfig,
  } = useLiveAPI({
    url: undefined, // Use default URL
    apiKey,
    initialConfig: {
      model: "models/gemini-2.5-flash-native-audio-preview-12-2025",
      // model: "models/gemini-2.0-flash-exp",
      systemInstruction: {
        parts: [{ text: systemInstruction }],
      },
      tools: [{ googleSearch: {} }],
      generationConfig: {
        responseModalities: "audio",
        speechConfig: {
          voiceConfig: {
            prebuiltVoiceConfig: { voiceName: "Aoede" },
          },
        },
      },
    },
  });

  // Determine if playing based on isModelTurn (must be declared right after hook)
  const isPlaying = isModelTurn;

  // Update config when explanation or pin changes
  useEffect(() => {
    if (pin) {
      const newSystemInstruction = `You are Atlantis, a news reporter AI assistant with access to web search, reporting on historical events to a single person.

Event Information:
- Title: ${pin.title}
- Date: ${pin.date}
- Location: ${pin.location_label}
- Category: ${pin.category}
- Significance Score: ${pin.significance_score}
${explanation ? `- Event Report: ${explanation.substring(0, 500)}...` : ''}

When you first start, introduce yourself as a news reporter and give a brief, engaging news-style report about this event. After that initial introduction, switch to answering questions in a conversational Q&A format.

You have access to web search capabilities. Use web search to find current, accurate information about this event and related topics. Provide detailed, well-researched answers based on web search results when relevant.

Respond in ${language}. Be conversational and helpful. Keep responses concise for voice output.`;

      setConfig({
        model: "models/gemini-2.5-flash-native-audio-preview-12-2025",
        // model: "models/gemini-2.0-flash-exp",
        systemInstruction: {
          parts: [{ text: newSystemInstruction }],
        },
        tools: [{ googleSearch: {} }],
        generationConfig: {
          responseModalities: "audio",
          speechConfig: {
            voiceConfig: {
              prebuiltVoiceConfig: { voiceName: "Aoede" },
            },
          },
        },
      });
    }
  }, [pin, explanation, language, setConfig]);

  // Set up auto-start when pin changes and article starts loading
  useEffect(() => {
    if (pin && explanationUrl) {
      shouldAutoStartRef.current = true;
    } else {
      shouldAutoStartRef.current = false;
    }
  }, [pin?.event_id, explanationUrl]);

  // Sync connection status with hook and notify parent
  useEffect(() => {
    if (connected) {
      setConnectionStatus("connected");
    } else if (connectionStatus === "connecting") {
      // Keep connecting state until we know for sure
    } else {
      setConnectionStatus("idle");
    }
  }, [connected, connectionStatus]);

  // Notify parent of state changes
  useEffect(() => {
    if (onStateChange) {
      onStateChange({
        connectionStatus,
        isPlaying,
        isExplaining,
      });
    }
  }, [connectionStatus, isPlaying, isExplaining, onStateChange]);


  // Set up audio recorder to send data when connected and setup is complete
  const audioRecorderRef = useRef<AudioRecorder | null>(null);
  const setupCompleteRef = useRef(false);
  const onDataHandlerRef = useRef<((base64: string) => void) | null>(null);

  useEffect(() => {
    if (!connected) {
      // Stop recorder when disconnected
      if (audioRecorderRef.current) {
        if (onDataHandlerRef.current) {
          audioRecorderRef.current.off("data", onDataHandlerRef.current);
          onDataHandlerRef.current = null;
        }
        audioRecorderRef.current.stop();
        audioRecorderRef.current = null;
      }
      setupCompleteRef.current = false;
      return;
    }

    // Wait for setupcomplete before starting audio recorder
    const onSetupComplete = () => {
      console.log("[LIVE API] Setup complete received");
      setupCompleteRef.current = true;

      // Create and start audio recorder after setup is complete
      if (!audioRecorderRef.current) {
        audioRecorderRef.current = new AudioRecorder(16000);
      }

      const audioRecorder = audioRecorderRef.current;

      const onData = (base64: string) => {
        if (!connected || !setupCompleteRef.current) return;
        try {
          client.sendRealtimeInput([
            {
              mimeType: "audio/pcm;rate=16000",
              data: base64,
            },
          ]);
        } catch (error) {
          if ((error as Error)?.message?.includes("WebSocket is not connected")) {
            // Ignore - connection may have closed
          } else {
            console.error("Error sending audio data:", error);
          }
        }
      };

      onDataHandlerRef.current = onData;
      audioRecorder.on("data", onData);
      audioRecorder.start().catch((error) => {
        console.error("Error starting audio recorder:", error);
      });

      // Send initial intro message
      if (!hasSentInitialIntroRef.current) {
        hasSentInitialIntroRef.current = true;
        console.log("[LIVE API] Sending initial reporter introduction request...");
        try {
          client.send([
            {
              text: "Please introduce yourself as a news reporter and give me a brief, engaging news-style report about this event.",
            },
          ]);
          console.log("[LIVE API] Initial introduction request sent");
        } catch (error) {
          console.error("[LIVE API] Error sending initial introduction:", error);
        }
      }
    };

    client.on("setupcomplete", onSetupComplete);

    return () => {
      if (audioRecorderRef.current && onDataHandlerRef.current) {
        audioRecorderRef.current.off("data", onDataHandlerRef.current);
        audioRecorderRef.current.stop();
        onDataHandlerRef.current = null;
      }
      client.off("setupcomplete", onSetupComplete);
    };
  }, [connected, client]);

  // Reset initial intro flag when pin changes (including navigation)
  useEffect(() => {
    hasSentInitialIntroRef.current = false;
  }, [pin?.event_id]);

  // Cleanup on unmount or pin change
  useEffect(() => {
    return () => {
      if (audioRecorderRef.current) {
        audioRecorderRef.current.stop();
        audioRecorderRef.current = null;
      }
      disconnect();
      hasSentInitialIntroRef.current = false;
    };
  }, [pin?.event_id, disconnect]);

  const handleStartLiveAPI = async () => {
    // Prevent starting if already connecting or connected
    if (connectionStatus === "connected" || connectionStatus === "connecting") {
      if (connectionStatus === "connected") {
        // Disconnect if already connected
        await disconnect();
        setConnectionStatus("idle");
        hasSentInitialIntroRef.current = false;
      }
      return;
    }

    if (!pin || !apiKey) {
      console.error("Cannot start Live API: missing pin or API key");
      setConnectionStatus("error");
      return;
    }

    setConnectionStatus("connecting");
    hasSentInitialIntroRef.current = false;
    shouldAutoStartRef.current = false; // Disable auto-start after manual/auto start

    try {
      const success = await connect();
      if (!success) {
        setConnectionStatus("error");
      }
    } catch (error) {
      console.error("Error starting Live API:", error);
      setConnectionStatus("error");
    }
  };

  const get_number_from_event_id = (event_id: string) => {
    const parts = event_id.split("_");
    return parseInt(parts[parts.length - 1]);
  }

  // Navigation logic
  const handleNavigate = async (direction: "prev" | "next") => {
    if (!pin || !onPinChange || allPins.length === 0) return;

    const currentIndex = allPins.findIndex((p) => p.event_id === pin.event_id);
    if (currentIndex === -1) return;

    let newIndex: number;
    if (direction === "prev") {
      newIndex = currentIndex > 0 ? currentIndex - 1 : allPins.length - 1;
    } else {
      newIndex = currentIndex < allPins.length - 1 ? currentIndex + 1 : 0;
    }

    const newPin = allPins[newIndex];
    if (newPin) {
      // Disconnect current session and reset state before navigating
      await disconnect();
      hasSentInitialIntroRef.current = false;
      setConnectionStatus("idle");
      onPinChange(newPin);
    }
  };

  // Calculate if previous/next navigation is available (always show when multiple pins, with wrap-around)
  const hasMultiplePins = allPins.length > 1;
  const hasPrevious = hasMultiplePins;
  const hasNext = hasMultiplePins;

  if (!pin) return null;

  return (
    <div className="event-dialog-overlay" onClick={onClose}>
      <div className="event-dialog-wrapper" onClick={(e) => e.stopPropagation()}>
        <div className="event-dialog">
          <button className="event-dialog-close" onClick={onClose}>
            ×
          </button>

          <h2>
            <span style={{ background: "#ffe066", color: "#111", borderRadius: "5px", padding: "2px 7px", marginRight: "8px", fontWeight: 700, fontFamily: "monospace" }}>
              #{get_number_from_event_id(pin.event_id)}
            </span>
            {pin.title}
          </h2>
          <p className="event-location">{pin.location_label}</p>
          <p className="event-date">{pin.date}</p>

          <div className="event-explanation">
            <div className="explanation-content">
              {isExplaining && !explanation ? (
                <div className="loading">Loading article...</div>
              ) : (
                <div className="explanation-text">
                  <ReactMarkdown remarkPlugins={[remarkBreaks]}>
                    {explanation}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Navigation arrows */}
        {hasPrevious && (
          <button
            className="event-dialog-nav-arrow event-dialog-nav-arrow-left"
            onClick={(e) => {
              e.stopPropagation();
              handleNavigate("prev");
            }}
            aria-label="Previous event"
            title="Previous event"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6"/>
            </svg>
          </button>
        )}
        {hasNext && (
          <button
            className="event-dialog-nav-arrow event-dialog-nav-arrow-right"
            onClick={(e) => {
              e.stopPropagation();
              handleNavigate("next");
            }}
            aria-label="Next event"
            title="Next event"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6"/>
            </svg>
          </button>
        )}
      </div>
    </div>
  );
}
