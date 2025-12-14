/**
 * React Query hooks for fetching event pins.
 */

import { useQuery } from "@tanstack/react-query";
import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { PinsRequest, PinsResponse } from "../types/events";

const API_BASE = "/api";

// Viewport change threshold (80%)
const REFETCH_THRESHOLD_PERCENT = 80;

/**
 * Calculate viewport dimensions and center from bbox.
 */
function getViewportMetrics(viewport: { bbox: { west: number; south: number; east: number; north: number } }) {
  const width = viewport.bbox.east - viewport.bbox.west;
  const height = viewport.bbox.north - viewport.bbox.south;
  const centerX = (viewport.bbox.west + viewport.bbox.east) / 2;
  const centerY = (viewport.bbox.south + viewport.bbox.north) / 2;
  return { width, height, centerX, centerY };
}

/**
 * Check if viewport has changed by more than the threshold (80%).
 * Returns true if refetch is needed.
 */
function shouldRefetch(
  oldViewport: { bbox: { west: number; south: number; east: number; north: number } },
  newViewport: { bbox: { west: number; south: number; east: number; north: number } }
): boolean {
  const oldMetrics = getViewportMetrics(oldViewport);
  const newMetrics = getViewportMetrics(newViewport);

  // Calculate percentage difference in x position
  const xDiffPercent = Math.abs(newMetrics.centerX - oldMetrics.centerX) / oldMetrics.width * 100;
  
  // Calculate percentage difference in y position
  const yDiffPercent = Math.abs(newMetrics.centerY - oldMetrics.centerY) / oldMetrics.height * 100;
  
  // Calculate percentage difference in width (for zoom out)
  const widthDiffPercent = Math.abs(newMetrics.width - oldMetrics.width) / oldMetrics.width * 100;
  
  // Calculate percentage difference in height (for zoom out)
  const heightDiffPercent = Math.abs(newMetrics.height - oldMetrics.height) / oldMetrics.height * 100;

  // Refetch if any change exceeds the threshold
  return (
    xDiffPercent > REFETCH_THRESHOLD_PERCENT ||
    yDiffPercent > REFETCH_THRESHOLD_PERCENT ||
    widthDiffPercent > REFETCH_THRESHOLD_PERCENT ||
    heightDiffPercent > REFETCH_THRESHOLD_PERCENT
  );
}

async function fetchPins(request: PinsRequest): Promise<PinsResponse> {
  const timestamp = new Date().toISOString();
  const callId = Math.random().toString(36).substring(7);
  
  console.log(`[fetchPins] 🚀 API call initiated`, {
    callId,
    timestamp,
    endpoint: `${API_BASE}/events/pins`,
    request: {
      date: request.date,
      language: request.language,
      max_pins: request.max_pins,
      viewport: {
        bbox: request.viewport.bbox,
        zoom: request.viewport.zoom,
      },
    },
    stackTrace: new Error().stack?.split('\n').slice(2, 6).join('\n'), // Show caller stack
  });

  const response = await fetch(`${API_BASE}/events/pins`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    console.error(`[fetchPins] ❌ API call failed`, {
      callId,
      status: response.status,
      statusText: response.statusText,
    });
    throw new Error(`Failed to fetch pins: ${response.statusText}`);
  }

  const data = await response.json();
  console.log(`[fetchPins] ✅ API call completed`, {
    callId,
    timestamp: new Date().toISOString(),
    pinsCount: data.pins?.length || 0,
  });

  return data;
}

export function usePins(
  date: string,
  viewport: PinsRequest["viewport"],
  language: string = "en",
  maxPins: number = 10,
  enabled: boolean = true
) {
  // Log date value to verify it's stable (YYYY-MM-DD format, no time)
  const prevDateRef_log = useRef<string | null>(null);
  useEffect(() => {
    if (prevDateRef_log.current !== date) {
      console.log(`[usePins] 📅 Date value`, {
        date,
        dateLength: date.length,
        dateType: typeof date,
        previous: prevDateRef_log.current,
        matchesYYYYMMDD: /^\d{4}-\d{2}-\d{2}$/.test(date),
        includesTime: date.includes('T') || date.includes(' '),
      });
      prevDateRef_log.current = date;
    }
  }, [date]);

  // Normalize viewport helper function - used for both comparison and query key
  // Round bbox to 2 decimal places (~1km precision) to group similar viewports together
  // This prevents duplicate queries when viewport changes slightly (e.g., from map animation)
  const normalizeViewport = useCallback((vp: PinsRequest["viewport"]) => {
    return {
      bbox: {
        west: Math.round(vp.bbox.west * 100) / 100,
        south: Math.round(vp.bbox.south * 100) / 100,
        east: Math.round(vp.bbox.east * 100) / 100,
        north: Math.round(vp.bbox.north * 100) / 100,
      },
      zoom: Math.round(vp.zoom * 10) / 10,
    };
  }, []);

  // Track the stabilized viewport that's used for the query key
  // This only updates when the viewport changes by more than 80%
  const [stabilizedViewport, setStabilizedViewport] = useState<PinsRequest["viewport"] | null>(null);

  // Reset stabilized viewport when date or language changes (fresh start)
  useEffect(() => {
    setStabilizedViewport(null);
  }, [date, language]);

  // Update stabilized viewport when current viewport changes by more than threshold
  // Add debounce to prevent rapid successive updates from causing duplicate queries
  useEffect(() => {
    if (!stabilizedViewport) {
      // Initial load: set stabilized viewport immediately
      setStabilizedViewport({ ...viewport });
      return;
    }

    // Normalize both viewports before comparison to ignore small differences
    // This prevents duplicate queries when map reports slightly different bounds after animation
    const normalizedStabilized = normalizeViewport(stabilizedViewport);
    const normalizedCurrent = normalizeViewport(viewport);
    
    // If normalized viewports are the same, ignore the change (it's just rounding differences)
    if (
      normalizedStabilized.bbox.west === normalizedCurrent.bbox.west &&
      normalizedStabilized.bbox.south === normalizedCurrent.bbox.south &&
      normalizedStabilized.bbox.east === normalizedCurrent.bbox.east &&
      normalizedStabilized.bbox.north === normalizedCurrent.bbox.north &&
      normalizedStabilized.zoom === normalizedCurrent.zoom
    ) {
      // Normalized viewports are identical, ignore this change
      return;
    }

    // Check if viewport has changed by more than 80% (using normalized values for comparison)
    if (shouldRefetch(normalizedStabilized, normalizedCurrent)) {
      // Debounce the update to prevent rapid successive changes
      // This prevents the case where viewport changes twice quickly (e.g., 
      // from programmatic update + map animation completion) causing duplicate queries
      const timeoutId = setTimeout(() => {
        setStabilizedViewport({ ...viewport });
      }, 300); // 300ms debounce

      return () => clearTimeout(timeoutId);
    }
  }, [viewport, stabilizedViewport, normalizeViewport]);

  const normalizedViewport = useMemo(() => {
    const vp = stabilizedViewport || viewport;
    return normalizeViewport(vp);
  }, [stabilizedViewport, viewport, normalizeViewport]);
  
  // Build query key
  const queryKey = useMemo(() => [
    "pins",
    date,
    normalizedViewport.bbox.west,
    normalizedViewport.bbox.south,
    normalizedViewport.bbox.east,
    normalizedViewport.bbox.north,
    normalizedViewport.zoom,
    language,
    maxPins,
  ], [date, normalizedViewport, language, maxPins]);

  // Track query key changes with detailed breakdown
  const prevQueryKeyRef = useRef<string | null>(null);
  const prevDateRef = useRef<string | null>(null);
  const prevNormalizedViewportRef = useRef<string | null>(null);
  
  useEffect(() => {
    const queryKeyStr = JSON.stringify(queryKey);
    const dateStr = date;
    const normalizedViewportStr = JSON.stringify(normalizedViewport);
    
    // Track individual component changes
    const changes: string[] = [];
    if (prevDateRef.current !== null && prevDateRef.current !== dateStr) {
      changes.push(`date: "${prevDateRef.current}" → "${dateStr}"`);
    }
    if (prevNormalizedViewportRef.current !== null && prevNormalizedViewportRef.current !== normalizedViewportStr) {
      changes.push(`normalizedViewport changed`);
    }
    
    // Update refs
    prevDateRef.current = dateStr;
    prevNormalizedViewportRef.current = normalizedViewportStr;
    
    if (prevQueryKeyRef.current !== null && prevQueryKeyRef.current !== queryKeyStr) {
      console.log(`[usePins] 🔑 Query key changed`, {
        previous: prevQueryKeyRef.current,
        current: queryKeyStr,
        queryKey,
        componentChanges: changes.length > 0 ? changes : ['unknown'],
        breakdown: {
          date: {
            previous: prevDateRef.current === null ? null : prevDateRef.current,
            current: dateStr,
            changed: prevDateRef.current !== null && prevDateRef.current !== dateStr,
          },
          normalizedViewport: {
            changed: prevNormalizedViewportRef.current !== null && prevNormalizedViewportRef.current !== normalizedViewportStr,
            current: normalizedViewport,
          },
          language,
          maxPins,
        },
      });
    }
    prevQueryKeyRef.current = queryKeyStr;
  }, [queryKey, date, normalizedViewport, language, maxPins]);

  // Track enabled state
  const isQueryEnabled = enabled && !!date && !!viewport && !!stabilizedViewport;
  const prevEnabledRef = useRef<boolean | null>(null);
  useEffect(() => {
    if (prevEnabledRef.current !== isQueryEnabled) {
      console.log(`[usePins] 🔄 Query enabled state changed`, {
        previous: prevEnabledRef.current,
        current: isQueryEnabled,
        reasons: {
          enabled,
          hasDate: !!date,
          hasViewport: !!viewport,
          hasStabilizedViewport: !!stabilizedViewport,
        },
      });
      prevEnabledRef.current = isQueryEnabled;
    }
  }, [isQueryEnabled, enabled, date, viewport, stabilizedViewport]);
  
  // Use normalized viewport in query key - this only changes when viewport changes > 80%
  return useQuery<PinsResponse, Error>({
    queryKey,
    queryFn: () => {
      console.log(`[usePins] 📞 useQuery.queryFn called (React Query is fetching)`, {
        queryKey,
        timestamp: new Date().toISOString(),
      });
      return fetchPins({
        date,
        viewport, // Still use current viewport for the actual request
        language,
        max_pins: maxPins,
      });
    },
    enabled: isQueryEnabled,
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}

