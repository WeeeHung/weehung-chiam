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
    const newCenter = [
      (viewport.bbox.west + viewport.bbox.east) / 2,
      (viewport.bbox.south + viewport.bbox.north) / 2,
    ];

    const centerChanged =
      Math.abs(prevCenter[0] - newCenter[0]) > 0.001 ||
      Math.abs(prevCenter[1] - newCenter[1]) > 0.001;
    const zoomChanged = Math.abs(prev.zoom - viewport.zoom) > 0.1;

    // Always animate if transitioning from world view to specific location, or if viewport changed significantly
    const shouldAnimate = isWorldView || centerChanged || zoomChanged;

    if (shouldAnimate) {
      console.log("Animating map to new viewport:", {
        center: newCenter,
        zoom: viewport.zoom,
        bbox: viewport.bbox,
        isTransitionFromWorldView: isWorldView,
        prevViewport: prev,
      });

      isProgrammaticMoveRef.current = true;
      map.current.flyTo({
        center: newCenter as [number, number],
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
    pins.forEach((pin) => {
      if (!map.current) return;

      const isSelected = pin.event_id === selectedPinId;
      const isRelated = relatedPinIds.includes(pin.event_id);

      const existingMarker = currentMarkers.get(pin.event_id);

      if (existingMarker) {
        // Update existing marker if selection state changed
        const markerEl = existingMarker.getElement();
        const wasSelected = markerEl.classList.contains("selected");
        const wasRelated = markerEl.classList.contains("related");

        if (wasSelected !== isSelected || wasRelated !== isRelated) {
          markerEl.className = `map-marker ${isSelected ? "selected" : ""} ${isRelated ? "related" : ""}`;
          markerEl.style.border = isSelected ? "3px solid #000" : "2px solid #fff";
        }

        // Update position if needed
        const [currentLng, currentLat] = existingMarker.getLngLat().toArray();
        if (Math.abs(currentLng - pin.lng) > 0.0001 || Math.abs(currentLat - pin.lat) > 0.0001) {
          existingMarker.setLngLat([pin.lng, pin.lat]);
        }
      } else {
        // Create new marker element
        const el = document.createElement("div");
        el.className = `map-marker ${isSelected ? "selected" : ""} ${isRelated ? "related" : ""}`;
        el.style.width = `${10 + pin.significance_score * 20}px`;
        el.style.height = `${10 + pin.significance_score * 20}px`;
        el.style.borderRadius = "50%";
        el.style.backgroundColor = getCategoryColor(pin.category);
        el.style.border = isSelected ? "3px solid #000" : "2px solid #fff";
        el.style.cursor = "pointer";
        el.style.boxShadow = "0 2px 4px rgba(0,0,0,0.3)";
        el.style.transition = "opacity 0.2s ease-in-out";
        el.title = pin.title;

        const Marker = (mapboxgl as any).Marker;
        const marker = new Marker(el)
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
