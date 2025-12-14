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
  language: string;
  onClose: () => void;
}

// Map language codes to supported API language codes
function getLanguageCode(lang: string): string {
  const languageMap: Record<string, string> = {
    en: "en-US",
    zh: "zh-CN", // Default to Simplified Chinese
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "zh-hans": "zh-CN",
    "zh-hant": "zh-TW",
    es: "es-ES",
    fr: "fr-FR",
    de: "de-DE",
    ja: "ja-JP",
    ko: "ko-KR",
    pt: "pt-BR",
    it: "it-IT",
    ru: "ru-RU",
    ar: "ar-SA",
    hi: "hi-IN",
  };
  return languageMap[lang.toLowerCase()] || "en-US";
}

type ConnectionStatus = "idle" | "connecting" | "connected" | "error";

export function EventDialog({ pin, language, onClose }: EventDialogProps) {
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

  // Sync connection status with hook
  useEffect(() => {
    if (connected) {
      setConnectionStatus("connected");
    } else if (connectionStatus === "connecting") {
      // Keep connecting state until we know for sure
    } else {
      setConnectionStatus("idle");
    }
  }, [connected, connectionStatus]);


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

  // Determine if playing based on isModelTurn
  const isPlaying = isModelTurn;

  if (!pin) return null;

  return (
    <div className="event-dialog-overlay" onClick={onClose}>
      <div className="event-dialog" onClick={(e) => e.stopPropagation()}>
        <button className="event-dialog-close" onClick={onClose}>
          ×
        </button>

        <h2>{pin.title}</h2>
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

      {/* Atlantis Bar */}
      <div className={`atlantis-bar ${isPlaying ? 'glowing' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div 
          className="atlantis-button"
          style={{ cursor: 'default', pointerEvents: 'none', textAlign: 'center' }}
        >
          {connectionStatus === "idle" && (isExplaining ? "Loading article..." : "Atlantis")}
          {connectionStatus === "connecting" && "Connecting..."}
          {connectionStatus === "connected" && (isPlaying ? "Atlantis is speaking..." : "Atlantis is listening...")}
          {connectionStatus === "error" && "Connection Error"}
        </div>
      </div>
    </div>
  );
}
