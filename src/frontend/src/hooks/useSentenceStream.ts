/**
 * Hook for streaming text sentence by sentence with animation.
 * Buffers chunks until complete sentences are detected, then queues them
 * and streams them out slowly with animation.
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { useSSE } from "./useSSE";

interface UseSentenceStreamOptions {
  onSentence?: (sentence: string) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
  animationDelay?: number; // Delay between sentences in ms (default: 100ms)
}

/**
 * Sentence-ending patterns:
 * - English: . ! ? followed by space/newline/end
 * - Chinese: 。！？ followed by space/newline/end
 * Matches punctuation followed by whitespace or end of string
 */
const SENTENCE_END_PATTERN = /([。！？.!?])(?=\s|$|\n)/;

export function useSentenceStream(
  url: string,
  options: UseSentenceStreamOptions = {}
) {
  const { onSentence, onDone, onError, animationDelay = 100 } = options;
  const [displayedText, setDisplayedText] = useState("");
  const bufferRef = useRef("");
  const sentenceQueueRef = useRef<string[]>([]);
  const isProcessingQueueRef = useRef(false);
  const animationTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onSentenceRef = useRef(onSentence);
  const onDoneRef = useRef(onDone);

  // Reset when URL changes
  useEffect(() => {
    setDisplayedText("");
    bufferRef.current = "";
    sentenceQueueRef.current = [];
    isProcessingQueueRef.current = false;
    if (animationTimeoutRef.current) {
      clearTimeout(animationTimeoutRef.current);
      animationTimeoutRef.current = null;
    }
  }, [url]);

  // Update refs when callbacks change
  useEffect(() => {
    onSentenceRef.current = onSentence;
    onDoneRef.current = onDone;
  }, [onSentence, onDone]);

  // Process sentence queue with animation
  const processQueue = useCallback(() => {
    if (isProcessingQueueRef.current || sentenceQueueRef.current.length === 0) {
      return;
    }

    isProcessingQueueRef.current = true;

    const processNext = () => {
      if (sentenceQueueRef.current.length === 0) {
        isProcessingQueueRef.current = false;
        return;
      }

      const sentence = sentenceQueueRef.current.shift()!;
      setDisplayedText((prev) => prev + sentence);
      onSentenceRef.current?.(sentence);

      if (sentenceQueueRef.current.length > 0) {
        animationTimeoutRef.current = setTimeout(processNext, animationDelay);
      } else {
        isProcessingQueueRef.current = false;
      }
    };

    processNext();
  }, [animationDelay]);

  const handleChunk = useCallback((chunk: string) => {
    // Handle plain text chunks
    const textChunk = chunk;

    // Add text chunk to buffer
    bufferRef.current += textChunk;

    // Process buffer to find complete sentences
    let remaining = bufferRef.current;

    while (remaining.length > 0) {
      const match = remaining.match(SENTENCE_END_PATTERN);
      
      if (match && match.index !== undefined) {
        // Found a sentence ending
        const sentenceEndIndex = match.index + match[1].length;
        const sentence = remaining.slice(0, sentenceEndIndex + 1);
        
        if (sentence.trim()) {
          // Add sentence to queue (preserve newlines)
          sentenceQueueRef.current.push(sentence);
        }
        
        // Remove processed sentence, keep any trailing whitespace/newlines
        remaining = remaining.slice(sentenceEndIndex + 1);
      } else {
        // Check for standalone newlines (not part of sentence endings)
        // These should be preserved and added to the queue
        if (remaining.startsWith("\n")) {
          sentenceQueueRef.current.push("\n");
          remaining = remaining.slice(1);
        } else {
          // No sentence ending found, keep remaining in buffer
          break;
        }
      }
    }

    // Update buffer with remaining text
    bufferRef.current = remaining;

    // Start processing queue if not already processing
    processQueue();
  }, [processQueue]);

  const handleDone = useCallback(() => {
    // Flush any remaining buffer as final content
    if (bufferRef.current.trim()) {
      sentenceQueueRef.current.push(bufferRef.current);
      bufferRef.current = "";
      processQueue();
    }

    // Wait for queue to finish before calling onDone
    const checkQueue = () => {
      if (sentenceQueueRef.current.length === 0 && !isProcessingQueueRef.current) {
        onDoneRef.current?.();
      } else {
        setTimeout(checkQueue, animationDelay);
      }
    };
    checkQueue();
  }, [processQueue, animationDelay]);

  const { isStreaming } = useSSE(url, {
    onChunk: handleChunk,
    onDone: handleDone,
    onError,
  });

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (animationTimeoutRef.current) {
        clearTimeout(animationTimeoutRef.current);
      }
    };
  }, []);

  return { displayedText, isStreaming };
}

