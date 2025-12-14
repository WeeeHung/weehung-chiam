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

        // All pins have the same design regardless of selection state
        if (wasSelected !== isSelected || wasRelated !== isRelated) {
          markerEl.className = "map-marker";
          // Keep border consistent for all pins
          const circleEl = markerEl.querySelector("div:first-child") as HTMLElement;
          if (circleEl) {
            circleEl.style.border = "2px solid #fff";
          }
        }

        // Update index number if it changed
        const indexEl = markerEl.querySelector(".pin-index") as HTMLElement;
        if (indexEl) {
          indexEl.textContent = pinIndex.toString();
        }

        // Only update position if coordinates actually changed
        const [currentLng, currentLat] = existingMarker.getLngLat().toArray();
        if (Math.abs(currentLng - pin.lng) > 0.0001 || Math.abs(currentLat - pin.lat) > 0.0001) {
          existingMarker.setLngLat([pin.lng, pin.lat]);
        }
      } else {
        // Create new marker element with pin shape
        // Pin shape: circular top with pointed bottom
        // All pins are the same size (not based on significance)
        const size = 30; // Fixed size for all pins
        const pinColor = getPositivityColor(pin.positivity_scale);
        
        const wrapper = document.createElement("div");
        wrapper.className = "map-marker";
        // Mapbox handles positioning via CSS transforms - don't interfere
        // Set explicit dimensions that Mapbox will use for anchor calculation
        wrapper.style.width = `${size * 1.3}px`;
        wrapper.style.height = `${size * 1.6}px`;
        wrapper.style.cursor = "pointer";
        wrapper.style.pointerEvents = "auto";
        // Ensure no positioning styles that could interfere with Mapbox transforms
        wrapper.style.margin = "0";
        wrapper.style.padding = "0";
        wrapper.style.boxSizing = "content-box";
        // Use relative positioning for tooltip, but ensure it doesn't affect Mapbox anchor calculation
        wrapper.style.position = "relative";
        wrapper.style.overflow = "visible";
        // Ensure wrapper maintains exact dimensions - tooltip is absolutely positioned so it won't affect layout
        wrapper.style.display = "block";
        
        // Create inner wrapper for visual transforms (hover/selected scaling)
        const inner = document.createElement("div");
        inner.className = "map-marker-inner";
        inner.style.width = "100%";
        inner.style.height = "100%";
        inner.style.display = "flex";
        inner.style.flexDirection = "column";
        inner.style.alignItems = "center";
        
        // Create circular top part
        const circle = document.createElement("div");
        circle.style.width = `${size}px`;
        circle.style.height = `${size}px`;
        circle.style.borderRadius = "50%";
        circle.style.backgroundColor = pinColor;
        circle.style.border = "2px solid #fff";
        circle.style.boxShadow = "0 2px 4px rgba(0,0,0,0.3)";
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
        
        inner.appendChild(circle);
        inner.appendChild(point);
        wrapper.appendChild(inner);
        
        // Create tooltip element with glassy design
        const tooltip = document.createElement("div");
        tooltip.className = "pin-tooltip";
        tooltip.style.position = "absolute";
        tooltip.style.bottom = "100%";
        tooltip.style.left = "50%";
        tooltip.style.transform = "translateX(-50%)";
        tooltip.style.marginBottom = "8px";
        tooltip.style.padding = "10px 16px";
        tooltip.style.width = "280px";
        tooltip.style.backgroundColor = "rgba(255, 255, 255, 0.65)";
        tooltip.style.backdropFilter = "blur(8px) saturate(180%)";
        tooltip.style.setProperty("-webkit-backdrop-filter", "blur(8px) saturate(180%)");
        tooltip.style.color = "#111827";
        tooltip.style.borderRadius = "8px";
        tooltip.style.fontSize = "13px";
        tooltip.style.fontWeight = "500";
        tooltip.style.whiteSpace = "normal";
        tooltip.style.textAlign = "center";
        tooltip.style.boxShadow = "0 4px 12px rgba(0, 0, 0, 0.15)";
        tooltip.style.border = "1px solid rgba(255, 255, 255, 0.3)";
        tooltip.style.opacity = "0";
        tooltip.style.visibility = "hidden";
        tooltip.style.transition = "opacity 0.2s, visibility 0.2s";
        tooltip.style.pointerEvents = "none";
        tooltip.style.zIndex = "1000";
        tooltip.style.wordWrap = "break-word";
        tooltip.style.boxSizing = "border-box";
        
        // Create tooltip arrow (pointing down) with glassy style
        const tooltipArrow = document.createElement("div");
        tooltipArrow.style.position = "absolute";
        tooltipArrow.style.top = "100%";
        tooltipArrow.style.left = "50%";
        tooltipArrow.style.transform = "translateX(-50%)";
        tooltipArrow.style.width = "0";
        tooltipArrow.style.height = "0";
        tooltipArrow.style.borderLeft = "8px solid transparent";
        tooltipArrow.style.borderRight = "8px solid transparent";
        tooltipArrow.style.borderTop = "8px solid rgba(255, 255, 255, 0.85)";
        tooltipArrow.style.filter = "drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1))";
        
        // Create tooltip content
        const tooltipTitle = document.createElement("div");
        tooltipTitle.textContent = pin.title;
        tooltipTitle.style.marginBottom = "6px";
        tooltipTitle.style.fontWeight = "600";
        tooltipTitle.style.fontSize = "15px";
        tooltipTitle.style.lineHeight = "1.4";
        tooltipTitle.style.color = "#111827";
        
        const tooltipReadMore = document.createElement("div");
        tooltipReadMore.textContent = "Read the full story...";
        tooltipReadMore.style.fontSize = "11px";
        tooltipReadMore.style.opacity = "0.7";
        tooltipReadMore.style.fontStyle = "italic";
        tooltipReadMore.style.color = "#374151";
        
        tooltip.appendChild(tooltipTitle);
        tooltip.appendChild(tooltipReadMore);
        tooltip.appendChild(tooltipArrow);
        wrapper.appendChild(tooltip);
        
        // Add hover event listeners
        wrapper.addEventListener("mouseenter", () => {
          tooltip.style.opacity = "1";
          tooltip.style.visibility = "visible";
        });
        
        wrapper.addEventListener("mouseleave", () => {
          tooltip.style.opacity = "0";
          tooltip.style.visibility = "hidden";
        });
        
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
