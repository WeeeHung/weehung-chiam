/**
 * Welcome Modal component - explains Atlantis and requests permissions.
 */

import { useState, useEffect } from "react";

interface WelcomeModalProps {
  onComplete: () => void;
}

interface PermissionState {
  mic: "prompt" | "granted" | "denied" | "unavailable";
  location: "prompt" | "granted" | "denied" | "unavailable";
}

export function WelcomeModal({ onComplete }: WelcomeModalProps) {
  const [permissions, setPermissions] = useState<PermissionState>({
    mic: "prompt",
    location: "prompt",
  });
  const [micRequested, setMicRequested] = useState(false);
  const [locationRequested, setLocationRequested] = useState(false);

  // Check initial permission states
  useEffect(() => {
    // Check microphone permission
    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: "microphone" as PermissionName }).then((result) => {
        setPermissions((prev) => ({ ...prev, mic: result.state as any }));
      }).catch(() => {
        setPermissions((prev) => ({ ...prev, mic: "unavailable" }));
      });
    } else {
      setPermissions((prev) => ({ ...prev, mic: "unavailable" }));
    }

    // Check geolocation permission
    if (navigator.permissions && navigator.permissions.query) {
      navigator.permissions.query({ name: "geolocation" as PermissionName }).then((result) => {
        setPermissions((prev) => ({ ...prev, location: result.state as any }));
      }).catch(() => {
        setPermissions((prev) => ({ ...prev, location: "unavailable" }));
      });
    } else {
      setPermissions((prev) => ({ ...prev, location: "unavailable" }));
    }
  }, []);

  const requestMicrophone = async () => {
    try {
      setMicRequested(true);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      // Stop the stream immediately - we just needed permission
      stream.getTracks().forEach((track) => track.stop());
      setPermissions((prev) => ({ ...prev, mic: "granted" }));
    } catch (error: any) {
      console.error("Microphone permission error:", error);
      if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
        setPermissions((prev) => ({ ...prev, mic: "denied" }));
      } else {
        setPermissions((prev) => ({ ...prev, mic: "unavailable" }));
      }
    }
  };

  const requestLocation = () => {
    setLocationRequested(true);
    if (!navigator.geolocation) {
      setPermissions((prev) => ({ ...prev, location: "unavailable" }));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      () => {
        setPermissions((prev) => ({ ...prev, location: "granted" }));
      },
      (error) => {
        console.error("Location permission error:", error);
        if (error.code === error.PERMISSION_DENIED) {
          setPermissions((prev) => ({ ...prev, location: "denied" }));
        } else {
          setPermissions((prev) => ({ ...prev, location: "unavailable" }));
        }
      },
      { timeout: 5000 }
    );
  };

  // Allow proceeding once both permissions have been requested (clicked) or are already determined
  const canProceed = 
    (micRequested || permissions.mic !== "prompt") &&
    (locationRequested || permissions.location !== "prompt");

  const handleProceed = () => {
    if (canProceed) {
      onComplete();
    }
  };

  return (
    <div className="welcome-modal-overlay">
      <div className="welcome-modal">
        <div className="welcome-modal-content">
          <h1 className="welcome-modal-title">Welcome to Atlantis</h1>
          
          <div className="welcome-section">
            <h2>What is Atlantis?</h2>
            <p>
              Atlantis is your AI-powered voice assistant for exploring world news and historical events on an interactive map. 
              Ask questions naturally, and Atlantis will help you discover events, navigate to locations, and learn about what's happening around the world.
            </p>
          </div>

          <div className="welcome-section">
            <h2>How to Interact</h2>
            <ul>
              <li><strong>Press and hold Spacebar</strong> to talk to Atlantis</li>
              <li>Release Spacebar when you're done speaking</li>
              <li>Click on map pins to explore events in detail</li>
              <li>Inside event dialogs, Atlantis can answer questions about the event</li>
            </ul>
          </div>

          <div className="welcome-section">
            <h2>Example Questions</h2>
            <div className="example-questions">
              <div className="example-question">
                <strong>Navigation:</strong> "Show me news from Tokyo" or "Take me to Paris"
              </div>
              <div className="example-question">
                <strong>Language:</strong> "Switch to Spanish" or "Show me news in Japanese"
              </div>
              <div className="example-question">
                <strong>Date:</strong> "Show me news from yesterday" or "What happened on January 1st?"
              </div>
              <div className="example-question">
                <strong>Events:</strong> Click any pin and ask "Tell me more about this" or "What caused this event?"
              </div>
            </div>
          </div>

          <div className="welcome-section permissions-section">
            <h2>Permissions Required</h2>
            <p className="permissions-description">
              To provide the best experience, Atlantis needs access to your microphone and location.
            </p>
            
            <div className="permission-item">
              <div className="permission-info">
                <span className="permission-icon">🎤</span>
                <div>
                  <strong>Microphone</strong>
                  <p>Needed for voice commands and interactive conversations</p>
                </div>
              </div>
              <div className="permission-status">
                {permissions.mic === "granted" && (
                  <span className="status-badge granted">✓ Granted</span>
                )}
                {permissions.mic === "denied" && (
                  <span className="status-badge denied">✗ Denied</span>
                )}
                {permissions.mic === "prompt" && (
                  <button 
                    className="permission-button"
                    onClick={requestMicrophone}
                    disabled={micRequested}
                  >
                    {micRequested ? "Requesting..." : "Grant Access"}
                  </button>
                )}
                {permissions.mic === "unavailable" && (
                  <span className="status-badge unavailable">Not Available</span>
                )}
              </div>
            </div>

            <div className="permission-item">
              <div className="permission-info">
                <span className="permission-icon">📍</span>
                <div>
                  <strong>Location</strong>
                  <p>Used to center the map on your location and show nearby events</p>
                </div>
              </div>
              <div className="permission-status">
                {permissions.location === "granted" && (
                  <span className="status-badge granted">✓ Granted</span>
                )}
                {permissions.location === "denied" && (
                  <span className="status-badge denied">✗ Denied</span>
                )}
                {permissions.location === "prompt" && (
                  <button 
                    className="permission-button"
                    onClick={requestLocation}
                    disabled={locationRequested}
                  >
                    {locationRequested ? "Requesting..." : "Grant Access"}
                  </button>
                )}
                {permissions.location === "unavailable" && (
                  <span className="status-badge unavailable">Not Available</span>
                )}
              </div>
            </div>
          </div>

          <button 
            className="proceed-button"
            onClick={handleProceed}
            disabled={!canProceed}
          >
            Get Started
          </button>
        </div>
      </div>
    </div>
  );
}

