/**
 * Simplified useLiveAPI hook for voice-only Live API integration
 * Based on reference implementation but without persona/topic dependencies
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  MultimodalLiveAPIClientConnection,
  MultimodalLiveClient,
} from "../lib/multimodal-live-client";
import {
  LiveConfig,
  ServerContent,
  isModelTurn,
} from "../types/multimodal-live-types";
import { AudioStreamer } from "../lib/audio-streamer";
import { audioContext } from "../lib/utils";
import VolMeterWorket from "../lib/worklets/vol-meter";
import { AudioRecorder } from "../lib/audio-recorder";

export type UseLiveAPIResults = {
  client: MultimodalLiveClient;
  setConfig: (config: LiveConfig) => void;
  config: LiveConfig;
  connected: boolean;
  connect: () => Promise<boolean>;
  disconnect: () => Promise<void>;
  volume: number;
  isModelTurn: boolean;
  audioRecorder: AudioRecorder | null;
};

export function useLiveAPI({
  url,
  apiKey,
  initialConfig,
}: MultimodalLiveAPIClientConnection & {
  initialConfig?: LiveConfig;
}): UseLiveAPIResults {
  const client = useMemo(
    () => new MultimodalLiveClient({ url, apiKey }),
    [url, apiKey],
  );
  const audioStreamerRef = useRef<AudioStreamer | null>(null);
  const audioRecorderRef = useRef<AudioRecorder | null>(null);

  const [connected, setConnected] = useState(false);

  // Initialize config state
  const [config, setConfig] = useState<LiveConfig>(() => {
    return (
      initialConfig || {
        model: "models/gemini-2.5-flash-native-audio-preview-12-2025",
        systemInstruction: {
          parts: [{ text: "You are a helpful assistant." }],
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
      }
    );
  });

  const [volume, setVolume] = useState(0);
  const [isModelTurnState, setIsModelTurnState] = useState(false);

  // Initialize audio recorder
  useEffect(() => {
    if (!audioRecorderRef.current) {
      audioRecorderRef.current = new AudioRecorder(16000);
    }
  }, []);

  // register audio for streaming server -> speakers
  useEffect(() => {
    if (!audioStreamerRef.current) {
      audioContext({ id: "audio-out" }).then((audioCtx: AudioContext) => {
        audioStreamerRef.current = new AudioStreamer(audioCtx);
        audioStreamerRef.current
          .addWorklet<any>("vumeter-out", VolMeterWorket, (ev: any) => {
            setVolume(ev.data.volume);
          })
          .then(() => {
            // Successfully added worklet
          });
      });
    }
  }, []);

  useEffect(() => {
    const onOpen = () => {
      console.log("LiveAPI Client: Connection opened.");
      setConnected(true);
    };
    const onClose = (event: CloseEvent) => {
      console.log("LiveAPI Client: Connection closed.", {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      });
      setConnected(false);
      setIsModelTurnState(false);
    };

    const stopAudioStreamer = () => {
      audioStreamerRef.current?.stop();
      setIsModelTurnState(false);
    };

    const onAudio = (data: ArrayBuffer) => {
      console.log(`Received audio data chunk (${data.byteLength} bytes)`);
      audioStreamerRef.current?.addPCM16(new Uint8Array(data));
    };

    const onContent = (content: ServerContent) => {
      console.log("Content received (modality=audio):", content);
      if (isModelTurn(content)) {
        console.log(
          `Received model turn content update with ${content.modelTurn.parts.length} parts.`
        );
      }
    };

    const onTurnComplete = () => {
      console.log("Turn complete");
      setIsModelTurnState(false);
    };

    const onIsModelTurn = () => {
      console.log("Model turn detected");
      setIsModelTurnState(true);
    };

    const onSetupComplete = () => {
      console.log("Setup complete - ready to receive audio");
    };

    client
      .on("open", onOpen)
      .on("close", onClose)
      .on("interrupted", stopAudioStreamer)
      .on("audio", onAudio)
      .on("content", onContent)
      .on("turncomplete", onTurnComplete)
      .on("ismodelturn", onIsModelTurn)
      .on("setupcomplete", onSetupComplete);

    return () => {
      client
        .off("open", onOpen)
        .off("close", onClose)
        .off("interrupted", stopAudioStreamer)
        .off("audio", onAudio)
        .off("content", onContent)
        .off("turncomplete", onTurnComplete)
        .off("ismodelturn", onIsModelTurn)
        .off("setupcomplete", onSetupComplete);
    };
  }, [client]);

  const connect = useCallback(async (): Promise<boolean> => {
    const systemInstructionText =
      config.systemInstruction?.parts?.[0]?.text ||
      "[System instruction text not available]";
    console.log("Final System Instruction being sent:", systemInstructionText);
    console.log(
      "Attempting to connect with config (modality=audio):",
      JSON.stringify(config, null, 2)
    );
    if (!config) {
      console.error("Connect failed: config has not been set");
      return false;
    }
    try {
      await client.connect(config);
      console.log("client.connect() promise resolved successfully.");
      return true;
    } catch (error) {
      console.error("Error during client.connect call:", error);
      setConnected(false);
      return false;
    }
  }, [client, config]);

  const disconnect = useCallback(async () => {
    audioRecorderRef.current?.stop();
    audioStreamerRef.current?.stop();
    client.disconnect();
  }, [client]);

  return {
    client,
    config,
    setConfig,
    connected,
    connect,
    disconnect,
    volume,
    isModelTurn: isModelTurnState,
    audioRecorder: audioRecorderRef.current,
  };
}
