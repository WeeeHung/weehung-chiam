/**
 * World map component with pins for events.
 * Uses Mapbox GL JS for rendering.
 */

import { useEffect, useRef, useState } from "react";
import "mapbox-gl/dist/mapbox-gl.css";
import { Pin, Viewport } from "../types/events";

// Import mapbox-gl - Vite handles CommonJS modules
import mapboxgl from "mapbox-gl";

interface WorldMapProps {
  pins: Pin[];
  viewport: Viewport;
  onViewportChange: (viewport: Viewport) => void;
  onPinClick: (pin: Pin) => void;
  selectedPinId?: string;
  relatedPinIds?: string[];
  mapboxToken: string;
  mapStyle?: string;
}

export function WorldMap({
  pins,
  viewport,
  onViewportChange,
  onPinClick,
  selectedPinId,
  relatedPinIds = [],
  mapboxToken,
  mapStyle = "mapbox://styles/mapbox/light-v11",
}: WorldMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<any>(null);
  const markersRef = useRef<Map<string, any>>(new Map());
  const [isInitialized, setIsInitialized] = useState(false);
  const isProgrammaticMoveRef = useRef(false);
  const lastViewportRef = useRef<Viewport | null>(null);

  // Initialize map
  useEffect(() => {
    if (!mapContainer.current || map.current || !mapboxToken) return;

    // Validate token format (basic check)
    if (!mapboxToken || mapboxToken === "YOUR_MAPBOX_TOKEN" || mapboxToken.trim() === "") {
      console.error("Invalid Mapbox token. Please set VITE_MAPBOX_TOKEN in your .env file.");
      return;
    }

    // Set access token
    (mapboxgl as any).accessToken = mapboxToken;

    const center: [number, number] = [
      (viewport.bbox.west + viewport.bbox.east) / 2,
      (viewport.bbox.south + viewport.bbox.north) / 2,
    ];

    map.current = new (mapboxgl as any).Map({
      container: mapContainer.current,
      style: mapStyle,
      center: center,
      zoom: viewport.zoom,

      // --- ADD THESE LINES TO STOP MOVEMENT ---
      inertia: 0,             // Stops the map instantly when you let go (no "sliding")
      dragRotate: false,      // Prevents the map from rotating (spinning compass)
      touchZoomRotate: false, // Prevents rotation on touch screens
      pitchWithRotate: false,  // Prevents tilting when you rotate
      // ----------------------------------------
      antialias: true,        // Smooth edges
    });

    map.current.on("load", () => {
      setIsInitialized(true);
    });

    map.current.on("error", (e: any) => {
      console.error("Mapbox error:", e);
      if (e.error && e.error.message) {
        console.error("Error details:", e.error.message);
      }
    });

    // Handle viewport changes with debouncing
    const moveTimeoutRef = { current: null as ReturnType<typeof setTimeout> | null };
    const lastReportedViewportRef = { current: null as Viewport | null };
    const handleMove = () => {
      if (!map.current || isProgrammaticMoveRef.current) {
        isProgrammaticMoveRef.current = false;
        return;
      }

      if (moveTimeoutRef.current) {
        clearTimeout(moveTimeoutRef.current);
      }

      moveTimeoutRef.current = setTimeout(() => {
        if (!map.current) return;
        const bounds = map.current.getBounds();
        const newViewport: Viewport = {
          bbox: {
            west: bounds.getWest(),
            south: bounds.getSouth(),
            east: bounds.getEast(),
            north: bounds.getNorth(),
          },
          zoom: map.current.getZoom(),
        };
        
        // Only update if viewport changed significantly (prevent micro-movements)
        const last = lastReportedViewportRef.current;
        if (last) {
          const lastCenter = [
            (last.bbox.west + last.bbox.east) / 2,
            (last.bbox.south + last.bbox.north) / 2,
          ];
          const newCenter = [
            (newViewport.bbox.west + newViewport.bbox.east) / 2,
            (newViewport.bbox.south + newViewport.bbox.north) / 2,
          ];
          
          const centerChanged =
            Math.abs(lastCenter[0] - newCenter[0]) > 0.01 ||
            Math.abs(lastCenter[1] - newCenter[1]) > 0.01;
          const zoomChanged = Math.abs(last.zoom - newViewport.zoom) > 0.1;
          
          // Only report if change is significant
          if (!centerChanged && !zoomChanged) {
            return;
          }
        }
        
        lastReportedViewportRef.current = newViewport;
        onViewportChange(newViewport);
      }, 500);
    };

    map.current.on("moveend", handleMove);
    map.current.on("zoomend", handleMove);
    
    // Store initial viewport
    lastViewportRef.current = viewport;

    return () => {
      if (moveTimeoutRef.current) {
        clearTimeout(moveTimeoutRef.current);
      }
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, [mapboxToken, mapStyle, onViewportChange]);

  // Update map style when it changes
  useEffect(() => {
    if (!map.current || !isInitialized) return;
    map.current.setStyle(mapStyle);
  }, [mapStyle, isInitialized]);

  // Smoothly animate to viewport when it changes programmatically
  useEffect(() => {
    if (!map.current || !isInitialized) {
      if (isInitialized) {
        lastViewportRef.current = viewport;
      }
      return;
    }

    // Check if viewport actually changed
    const prev = lastViewportRef.current;
    if (!prev) {
      lastViewportRef.current = viewport;
      return;
    }

    // Get current map state to compare with target viewport
    const currentCenter = map.current.getCenter();
    const currentZoom = map.current.getZoom();
    
    const targetCenter = [
      (viewport.bbox.west + viewport.bbox.east) / 2,
      (viewport.bbox.south + viewport.bbox.north) / 2,
    ];
    
    // Check if map is already at the target position (within tolerance)
    // Use larger thresholds to prevent micro-movements: 0.01 degrees ≈ 1km
    const centerDistance = Math.sqrt(
      Math.pow(currentCenter.lng - targetCenter[0], 2) +
      Math.pow(currentCenter.lat - targetCenter[1], 2)
    );
    const zoomDiff = Math.abs(currentZoom - viewport.zoom);
    
    // If map is already close to target, don't animate
    if (centerDistance < 0.01 && zoomDiff < 0.1) {
      lastViewportRef.current = viewport;
      return;
    }

    // Check if previous viewport was the default/world viewport
    // (bbox covering entire world: west=-180, east=180, south=-90, north=90, zoom=2)
    const isWorldView = 
      prev.bbox.west <= -179 &&
      prev.bbox.east >= 179 &&
      prev.bbox.south <= -89 &&
      prev.bbox.north >= 89 &&
      prev.zoom <= 3;

    const prevCenter = [
      (prev.bbox.west + prev.bbox.east) / 2,
      (prev.bbox.south + prev.bbox.north) / 2,
    ];

    const centerChanged =
      Math.abs(prevCenter[0] - targetCenter[0]) > 0.01 ||
      Math.abs(prevCenter[1] - targetCenter[1]) > 0.01;
    const zoomChanged = Math.abs(prev.zoom - viewport.zoom) > 0.1;

    // Always animate if transitioning from world view to specific location, or if viewport changed significantly
    const shouldAnimate = isWorldView || centerChanged || zoomChanged;

    if (shouldAnimate) {
      console.log("Animating map to new viewport:", {
        center: targetCenter,
        zoom: viewport.zoom,
        bbox: viewport.bbox,
        isTransitionFromWorldView: isWorldView,
        prevViewport: prev,
      });

      isProgrammaticMoveRef.current = true;
      map.current.flyTo({
        center: targetCenter as [number, number],
        zoom: viewport.zoom,
        duration: 1500, // 2 second smooth animation
        essential: true,
      });
    }

    lastViewportRef.current = viewport;
  }, [viewport, isInitialized]);

  // Update pins (optimized to prevent flickering)
  useEffect(() => {
    if (!map.current || !isInitialized) return;

    const currentMarkers = markersRef.current;
    const newPinIds = new Set(pins.map((pin) => pin.event_id));

    // Remove markers that are no longer in the pins list
    for (const [pinId, marker] of currentMarkers.entries()) {
      if (!newPinIds.has(pinId)) {
        marker.remove();
        currentMarkers.delete(pinId);
      }
    }

    // Update or add markers
    pins.forEach((pin) => {
      if (!map.current) return;

      const existingMarker = currentMarkers.get(pin.event_id);

      if (existingMarker) {
        // Update position if coordinates actually changed
        const [currentLng, currentLat] = existingMarker.getLngLat().toArray();
        if (Math.abs(currentLng - pin.lng) > 0.0001 || Math.abs(currentLat - pin.lat) > 0.0001) {
          existingMarker.setLngLat([pin.lng, pin.lat]);
        }
      } else {
        const Marker = (mapboxgl as any).Marker;
        const Popup = (mapboxgl as any).Popup;
        const pinColor = getPositivityColor(pin.positivity_scale);
        
        // Create popup for tooltip with glass panel design
        const popupHTML = `
          <div style="
            padding: 10px 16px;
            background-color: rgba(255, 255, 255, 0.65);
            backdrop-filter: blur(8px) saturate(180%);
            -webkit-backdrop-filter: blur(8px) saturate(180%);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            max-width: 250px;
            text-align: center;
          ">
            <div style="
              margin-bottom: 6px;
              font-weight: 600;
              font-size: 15px;
              line-height: 1.4;
              color: #111827;
            ">${pin.title}</div>
            <div style="
              font-size: 11px;
              opacity: 0.7;
              font-style: italic;
              color: #374151;
            ">Read the full story...</div>
          </div>
        `;
        
        const popup = new Popup({
          closeButton: false,
          closeOnClick: false,
          className: 'pin-popup',
          maxWidth: 'none'
        }).setHTML(popupHTML);
        
        // Create default marker with custom color based on positivity scale
        const marker = new Marker({
          color: pinColor
        })
          .setLngLat([pin.lng, pin.lat])
          .setPopup(popup)
          .addTo(map.current);
        
        // Show popup on hover, hide on mouse leave (hover-only behavior)
        const markerEl = marker.getElement();
        let hoverTimeout: ReturnType<typeof setTimeout> | null = null;
        
        const showPopup = () => {
          if (hoverTimeout) {
            clearTimeout(hoverTimeout);
            hoverTimeout = null;
          }
          if (!popup.isOpen()) {
            popup.addTo(map.current);
          }
        };
        
        const hidePopup = () => {
          if (hoverTimeout) {
            clearTimeout(hoverTimeout);
          }
          hoverTimeout = setTimeout(() => {
            if (popup.isOpen()) {
              popup.remove();
            }
            hoverTimeout = null;
          }, 50); // Small delay to allow moving from marker to popup
        };
        
        markerEl.addEventListener("mouseenter", showPopup);
        markerEl.addEventListener("mouseleave", hidePopup);
        
        // Handle popup hover to keep it open when hovering over it
        popup.on('open', () => {
          const popupEl = popup.getElement();
          if (popupEl) {
            popupEl.addEventListener("mouseenter", () => {
              if (hoverTimeout) {
                clearTimeout(hoverTimeout);
                hoverTimeout = null;
              }
            });
            popupEl.addEventListener("mouseleave", hidePopup);
          }
        });
        
        markerEl.addEventListener("click", () => onPinClick(pin));

        currentMarkers.set(pin.event_id, marker);
      }
    });
  }, [pins, isInitialized, selectedPinId, relatedPinIds, onPinClick]);


  return (
    <div ref={mapContainer} className="world-map" style={{ width: "100%", height: "100%" }} />
  );
}

/**
 * Get color based on positivity scale (0-1).
 * 1.0 (positive) = green, 0.0 (negative) = red, 0.5 (neutral) = yellow/orange
 */
function getPositivityColor(positivityScale: number): string {
  // Clamp value between 0 and 1
  const scale = Math.max(0, Math.min(1, positivityScale));
  
  // Interpolate between red (0) and green (1)
  // Red: rgb(239, 68, 68) = #ef4444
  // Green: rgb(34, 197, 94) = #22c55e
  // Yellow (neutral 0.5): rgb(234, 179, 8) = #eab308
  
  if (scale <= 0.5) {
    // Interpolate from red to yellow (0 to 0.5)
    const t = scale * 2; // 0 to 1 for the red-yellow range
    const r = Math.round(239 + (234 - 239) * t);
    const g = Math.round(68 + (179 - 68) * t);
    const b = Math.round(68 + (8 - 68) * t);
    return `rgb(${r}, ${g}, ${b})`;
  } else {
    // Interpolate from yellow to green (0.5 to 1.0)
    const t = (scale - 0.5) * 2; // 0 to 1 for the yellow-green range
    const r = Math.round(234 + (34 - 234) * t);
    const g = Math.round(179 + (197 - 179) * t);
    const b = Math.round(8 + (94 - 8) * t);
    return `rgb(${r}, ${g}, ${b})`;
  }
}
