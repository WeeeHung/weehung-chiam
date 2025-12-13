/**
 * World map component with pins for events.
 * Uses Mapbox GL JS for rendering.
 */

import React, { useEffect, useRef, useState, useCallback } from "react";
import "mapbox-gl/dist/mapbox-gl.css";
import { Pin, Viewport } from "../types/events";

// Import mapbox-gl - Vite handles CommonJS modules
// @ts-expect-error - mapbox-gl doesn't have proper ESM default export
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
    const moveTimeoutRef = { current: null as NodeJS.Timeout | null };
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
    const currentBounds = map.current.getBounds();
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
        duration: 2000, // 2 second smooth animation
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
    pins.forEach((pin, index) => {
      if (!map.current) return;

      const isSelected = pin.event_id === selectedPinId;
      const isRelated = relatedPinIds.includes(pin.event_id);
      const pinIndex = index + 1; // 1-based index for display

      const existingMarker = currentMarkers.get(pin.event_id);

      if (existingMarker) {
        // Update existing marker if selection state changed
        const markerEl = existingMarker.getElement();
        const wasSelected = markerEl.classList.contains("selected");
        const wasRelated = markerEl.classList.contains("related");

        if (wasSelected !== isSelected || wasRelated !== isRelated) {
          markerEl.className = `map-marker ${isSelected ? "selected" : ""} ${isRelated ? "related" : ""}`;
          // Update border on the circle element (first child div)
          const circleEl = markerEl.querySelector("div:first-child") as HTMLElement;
          if (circleEl) {
            circleEl.style.border = isSelected ? "3px solid #000" : "2px solid #fff";
          }
        }

        // Update index number if it changed
        const indexEl = markerEl.querySelector(".pin-index") as HTMLElement;
        if (indexEl) {
          indexEl.textContent = pinIndex.toString();
        }

        // Update position if needed
        const [currentLng, currentLat] = existingMarker.getLngLat().toArray();
        if (Math.abs(currentLng - pin.lng) > 0.0001 || Math.abs(currentLat - pin.lat) > 0.0001) {
          existingMarker.setLngLat([pin.lng, pin.lat]);
        }
      } else {
        // Create new marker element with pin shape
        // Pin shape: circular top with pointed bottom
        // All pins are the same size (not based on significance)
        const size = 30; // Fixed size for all pins
        const pinColor = getCategoryColor(pin.category);
        
        const wrapper = document.createElement("div");
        wrapper.className = `map-marker ${isSelected ? "selected" : ""} ${isRelated ? "related" : ""}`;
        wrapper.style.position = "relative";
        wrapper.style.width = `${size * 1.3}px`;
        wrapper.style.height = `${size * 1.6}px`;
        wrapper.style.display = "flex";
        wrapper.style.flexDirection = "column";
        wrapper.style.alignItems = "center";
        wrapper.style.cursor = "pointer";
        
        // Create circular top part
        const circle = document.createElement("div");
        circle.style.width = `${size}px`;
        circle.style.height = `${size}px`;
        circle.style.borderRadius = "50%";
        circle.style.backgroundColor = pinColor;
        circle.style.border = isSelected ? "3px solid #000" : "2px solid #fff";
        circle.style.boxShadow = "0 2px 4px rgba(0,0,0,0.3)";
        circle.style.position = "relative";
        circle.style.display = "flex";
        circle.style.alignItems = "center";
        circle.style.justifyContent = "center";
        circle.style.zIndex = "2";
        
        // Create pointed bottom (triangle)
        const point = document.createElement("div");
        const pointSize = size * 0.25;
        point.style.width = "0";
        point.style.height = "0";
        point.style.borderLeft = `${pointSize}px solid transparent`;
        point.style.borderRight = `${pointSize}px solid transparent`;
        point.style.borderTop = `${size * 0.4}px solid ${pinColor}`;
        point.style.marginTop = `-${size * 0.15}px`; // Overlap with circle slightly
        point.style.filter = "drop-shadow(0 2px 2px rgba(0,0,0,0.3))";
        
        // Create index number element
        const indexEl = document.createElement("span");
        indexEl.className = "pin-index";
        indexEl.textContent = pinIndex.toString();
        indexEl.style.color = "#ffffff";
        indexEl.style.fontSize = `${Math.max(10, size * 0.4)}px`;
        indexEl.style.fontWeight = "bold";
        indexEl.style.textShadow = "0 1px 2px rgba(0,0,0,0.7)";
        indexEl.style.userSelect = "none";
        indexEl.style.pointerEvents = "none";
        circle.appendChild(indexEl);
        
        wrapper.appendChild(circle);
        wrapper.appendChild(point);
        wrapper.title = pin.title;
        
        const el = wrapper;

        // Create marker with anchor at bottom center (the pin point)
        // This ensures the pin point aligns with the lat/lng coordinate
        const Marker = (mapboxgl as any).Marker;
        const marker = new Marker({
          element: el,
          anchor: 'bottom', // Anchor at the bottom center of the pin (the point)
        })
          .setLngLat([pin.lng, pin.lat])
          .addTo(map.current);

        el.addEventListener("click", () => onPinClick(pin));

        currentMarkers.set(pin.event_id, marker);
      }
    });
  }, [pins, isInitialized, selectedPinId, relatedPinIds, onPinClick]);

  return (
    <div ref={mapContainer} className="world-map" style={{ width: "100%", height: "100%" }} />
  );
}

function getCategoryColor(category: string): string {
  const colors: Record<string, string> = {
    politics: "#3b82f6",
    conflict: "#ef4444",
    culture: "#8b5cf6",
    science: "#10b981",
    economics: "#f59e0b",
    other: "#6b7280",
  };
  return colors[category] || colors.other;
}
