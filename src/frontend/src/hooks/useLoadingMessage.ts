/**
 * Hook for streaming loading messages with typewriter effect.
 * Cycles through fixed messages, typing them out and deleting them.
 */

import { useState, useEffect, useRef } from "react";

const LOADING_MESSAGES = [
    "loading local news reporter...",
    "loading events...",
    "loading historian..."
];

interface UseLoadingMessageOptions {
  enabled?: boolean;
  typeSpeed?: number; // ms per character when typing
  deleteSpeed?: number; // ms per character when deleting
  pauseAfterComplete?: number; // ms to pause after completing a message
  pauseAfterDelete?: number; // ms to pause after deleting a message
}

export function useLoadingMessage(options: UseLoadingMessageOptions = {}) {
  const {
    enabled = true,
    typeSpeed = 200,
    deleteSpeed = 50,
    pauseAfterComplete = 1000,
    pauseAfterDelete = 300,
  } = options;

  const [displayedText, setDisplayedText] = useState("");
  const [messageIndex, setMessageIndex] = useState(0);
  const [isTyping, setIsTyping] = useState(true);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled) {
      setDisplayedText("");
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      return;
    }

    const currentMessage = LOADING_MESSAGES[messageIndex];
    const currentLength = displayedText.length;
    const targetLength = currentMessage.length;

    if (isTyping) {
      // Typing mode: add characters
      if (currentLength < targetLength) {
        timeoutRef.current = setTimeout(() => {
          setDisplayedText(currentMessage.slice(0, currentLength + 1));
        }, typeSpeed);
      } else {
        // Finished typing, pause then switch to deleting
        timeoutRef.current = setTimeout(() => {
          setIsTyping(false);
        }, pauseAfterComplete);
      }
    } else {
      // Deleting mode: remove characters
      if (currentLength > 7) {
        timeoutRef.current = setTimeout(() => {
          setDisplayedText(currentMessage.slice(0, currentLength - 1));
        }, deleteSpeed);
      } else {
        // Finished deleting, pause then move to next message
        timeoutRef.current = setTimeout(() => {
          setMessageIndex((prev) => (prev + 1) % LOADING_MESSAGES.length);
          setIsTyping(true);
        }, pauseAfterDelete);
      }
    }

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [enabled, displayedText, messageIndex, isTyping, typeSpeed, deleteSpeed, pauseAfterComplete, pauseAfterDelete]);

  // Reset when enabled changes
  useEffect(() => {
    if (enabled) {
      setDisplayedText("");
      setMessageIndex(0);
      setIsTyping(true);
    }
  }, [enabled]);

  return displayedText;
}

