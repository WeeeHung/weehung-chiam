/**
 * Event dialog component for displaying event details and Q&A.
 */

import React, { useState, useEffect } from "react";
import { Pin, ChatMessage } from "../types/events";
import { useSSE, useSSEPost } from "../hooks/useSSE";

interface EventDialogProps {
  pin: Pin | null;
  language: string;
  onClose: () => void;
}

export function EventDialog({ pin, language, onClose }: EventDialogProps) {
  const [question, setQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [explanation, setExplanation] = useState("");

  // Stream explanation
  const explanationUrl = pin
    ? `/api/events/${pin.event_id}/explain/stream?language=${language}`
    : "";
  
  // Use useCallback to memoize the onChunk callback to prevent reconnections
  const handleExplanationChunk = React.useCallback((chunk: string) => {
    setExplanation((prev) => prev + chunk);
  }, []);

  const { isStreaming: isExplaining } = useSSE(explanationUrl, {
    onChunk: handleExplanationChunk,
  });

  // Reset when pin changes
  useEffect(() => {
    if (pin) {
      setExplanation("");
      setChatHistory([]);
      setQuestion("");
    }
  }, [pin?.event_id]);

  const handleSendQuestion = () => {
    if (!pin || !question.trim()) return;

    const newHistory: ChatMessage[] = [
      ...chatHistory,
      { role: "user", content: question },
    ];
    setChatHistory(newHistory);
    setQuestion("");

    // Stream chat response
    const chatUrl = `/api/events/${pin.event_id}/chat/stream`;
    const chatBody = {
      language,
      question,
      history: chatHistory,
    };

    // Use fetch for POST SSE
    fetch(chatUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(chatBody),
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Chat request failed");

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let assistantResponse = "";

        if (!reader) return;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const chunk = line.slice(6);
              assistantResponse += chunk;
            } else if (line.startsWith("event: done")) {
              break;
            }
          }
        }

        setChatHistory([
          ...newHistory,
          { role: "assistant", content: assistantResponse },
        ]);
      })
      .catch((error) => {
        console.error("Chat error:", error);
      });
  };

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
          <h3>Why this matters</h3>
          <p className="event-one-liner">{pin.one_liner}</p>

          <h3>Explanation</h3>
          <div className="explanation-content">
            {isExplaining && !explanation ? (
              <div className="loading">Loading explanation...</div>
            ) : (
              <div className="explanation-text">{explanation}</div>
            )}
          </div>
        </div>

        <div className="event-chat">
          <h3>Ask a question</h3>
          <div className="chat-history">
            {chatHistory.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.role}`}>
                <strong>{msg.role === "user" ? "You" : "Assistant"}:</strong>
                <p>{msg.content}</p>
              </div>
            ))}
          </div>
          <div className="chat-input">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === "Enter") {
                  handleSendQuestion();
                }
              }}
              placeholder="Ask about this event..."
            />
            <button onClick={handleSendQuestion} disabled={!question.trim()}>
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

