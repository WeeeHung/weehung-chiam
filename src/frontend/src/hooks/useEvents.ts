/**
 * React Query hooks for fetching event pins.
 */

import { useQuery } from "@tanstack/react-query";
import { PinsRequest, PinsResponse, Pin } from "../types/events";

const API_BASE = "/api";

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
  // Normalize bbox values to prevent micro-changes from triggering new queries
  // Round to 2 decimal places (~1km precision) to avoid floating point precision issues
  const normalizedBbox = {
    west: Math.round(viewport.bbox.west * 100) / 100,
    south: Math.round(viewport.bbox.south * 100) / 100,
    east: Math.round(viewport.bbox.east * 100) / 100,
    north: Math.round(viewport.bbox.north * 100) / 100,
  };
  
  // Flatten bbox into query key for stable comparison
  return useQuery<PinsResponse, Error>({
    queryKey: [
      "pins",
      date,
      normalizedBbox.west,
      normalizedBbox.south,
      normalizedBbox.east,
      normalizedBbox.north,
      Math.round(viewport.zoom * 10) / 10, // Round zoom to 1 decimal place
      language,
      maxPins,
    ],
    queryFn: () =>
      fetchPins({
        date,
        viewport,
        language,
        max_pins: maxPins,
      }),
    enabled: enabled && !!date && !!viewport,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

