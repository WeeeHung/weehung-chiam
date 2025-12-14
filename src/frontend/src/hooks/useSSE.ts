/**
 * Custom hook for Server-Sent Events (SSE) streaming.
 */

import { useEffect, useRef, useState } from "react";

interface UseSSEOptions {
  onChunk?: (chunk: string) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
}

export function useSSE(url: string, options: UseSSEOptions = {}) {
  const { onChunk, onDone, onError } = options;
  const [data, setData] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  
  // Store callbacks in refs to avoid recreating connections
  const onChunkRef = useRef(onChunk);
  const onDoneRef = useRef(onDone);
  const onErrorRef = useRef(onError);
  
  // Update refs when callbacks change
  useEffect(() => {
    onChunkRef.current = onChunk;
    onDoneRef.current = onDone;
    onErrorRef.current = onError;
  }, [onChunk, onDone, onError]);

  useEffect(() => {
    if (!url) return;

    // Close existing connection if any
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    setIsStreaming(true);
    setData("");

    // Use EventSource for GET requests
    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    // Listen for custom "chunk" event type
    eventSource.addEventListener("chunk", (event: MessageEvent) => {
      const chunk = event.data;
      setData((prev) => prev + chunk);
      onChunkRef.current?.(chunk);
    });

    // Also handle default message events (for compatibility)
    eventSource.onmessage = (event) => {
      const chunk = event.data;
      setData((prev) => prev + chunk);
      onChunkRef.current?.(chunk);
    };

    eventSource.addEventListener("done", () => {
      setIsStreaming(false);
      onDoneRef.current?.();
      eventSource.close();
    });

    eventSource.onerror = () => {
      setIsStreaming(false);
      onErrorRef.current?.(new Error("SSE connection error"));
      eventSource.close();
    };

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [url]); // Only depend on url, not callbacks

  const stop = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      setIsStreaming(false);
    }
  };

  return { data, isStreaming, stop };
}

/**
 * Hook for POST-based SSE streaming (for chat).
 */
export function useSSEPost(
  url: string,
  body: any,
  options: UseSSEOptions = {}
) {
  const { onChunk, onDone, onError } = options;
  const [data, setData] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!url || !body) return;

    setIsStreaming(true);
    setData("");

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: abortController.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error("No response body");
        }

        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          let eventData: string[] = [];
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              // Collect data lines (SSE spec: multiple data lines are concatenated with newlines)
              eventData.push(line.slice(6));
            } else if (line.startsWith("event: done") || (line === "" && eventData.length > 0)) {
              // End of event - concatenate all data lines with newlines
              if (eventData.length > 0) {
                const chunk = eventData.join("\n");
                setData((prev) => prev + chunk);
                onChunk?.(chunk);
                eventData = [];
              }
              if (line.startsWith("event: done")) {
                setIsStreaming(false);
                onDone?.();
                return;
              }
            } else if (line === "" && eventData.length > 0) {
              // Empty line after data lines - flush accumulated data
              const chunk = eventData.join("\n");
              setData((prev) => prev + chunk);
              onChunk?.(chunk);
              eventData = [];
            }
          }
        }

        setIsStreaming(false);
        onDone?.();
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          setIsStreaming(false);
          onError?.(error);
        }
      });

    return () => {
      abortController.abort();
    };
  }, [url, JSON.stringify(body), onChunk, onDone, onError]);

  const stop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsStreaming(false);
    }
  };

  return { data, isStreaming, stop };
}

