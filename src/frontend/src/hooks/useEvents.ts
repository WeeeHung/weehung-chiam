/**
 * React Query hooks for fetching event pins.
 */

import { useQuery } from "@tanstack/react-query";
import { useState, useEffect, useMemo } from "react";
import { PinsRequest, PinsResponse } from "../types/events";

const API_BASE = "/api";

// Distance threshold in kilometers (50km)
const REFETCH_DISTANCE_KM = 50;

/**
 * Calculate the distance between two lat/lng points using the Haversine formula.
 * Returns distance in kilometers.
 */
function calculateDistance(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number
): number {
  const R = 6371; // Earth's radius in kilometers
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) *
      Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

async function fetchPins(request: PinsRequest): Promise<PinsResponse> {
  const response = await fetch(`${API_BASE}/events/pins`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch pins: ${response.statusText}`);
  }

  return response.json();
}

export function usePins(
  date: string,
  viewport: PinsRequest["viewport"],
  language: string = "en",
  maxPins: number = 8,
  enabled: boolean = true
) {
  // Calculate current center from viewport
  const currentCenter = useMemo(() => {
    return {
      lat: (viewport.bbox.south + viewport.bbox.north) / 2,
      lng: (viewport.bbox.west + viewport.bbox.east) / 2,
    };
  }, [viewport]);

  // Track the stabilized center that's used for the query key
  // This only updates when the map center moves more than 50km
  const [stabilizedCenter, setStabilizedCenter] = useState<{
    lat: number;
    lng: number;
  } | null>(null);

  // Update stabilized center when current center moves more than threshold
  useEffect(() => {
    if (!stabilizedCenter) {
      // Initial load: set stabilized center immediately
      setStabilizedCenter({ ...currentCenter });
      return;
    }

    // Calculate distance from last stabilized center
    const distance = calculateDistance(
      stabilizedCenter.lat,
      stabilizedCenter.lng,
      currentCenter.lat,
      currentCenter.lng
    );

    // Only update stabilized center (which triggers refetch) if moved more than threshold
    if (distance > REFETCH_DISTANCE_KM) {
      setStabilizedCenter({ ...currentCenter });
    }
  }, [currentCenter.lat, currentCenter.lng, stabilizedCenter]);

  // Normalize the stabilized center used in query key to prevent micro-changes
  // Round to 3 decimal places (~100m precision)
  const normalizedCenter = useMemo(() => {
    const center = stabilizedCenter || currentCenter;
    return {
      lat: Math.round(center.lat * 1000) / 1000,
      lng: Math.round(center.lng * 1000) / 1000,
    };
  }, [stabilizedCenter, currentCenter]);
  
  // Flatten bbox into query key for stable comparison
  // Use normalizedCenter in query key - this only changes when center moves > 50km
  return useQuery<PinsResponse, Error>({
    queryKey: [
      "pins",
      date,
      normalizedCenter.lat,
      normalizedCenter.lng,
      Math.round(viewport.zoom * 10) / 10, // Round zoom to 1 decimal place
      language,
      maxPins,
    ],
    queryFn: () =>
      fetchPins({
        date,
        viewport, // Still use current viewport for the actual request
        language,
        max_pins: maxPins,
      }),
    enabled: enabled && !!date && !!viewport && !!stabilizedCenter,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

