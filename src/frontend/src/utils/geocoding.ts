/**
 * Geocoding utility for converting location names to coordinates.
 * Uses Nominatim (OpenStreetMap) API.
 */

export interface GeocodeResult {
  lat: number;
  lng: number;
  display_name?: string;
}

/**
 * Geocode a location name to lat/lng coordinates using Nominatim.
 * 
 * @param locationName - Name of the location (city, country, etc.)
 * @returns Promise resolving to geocode result or null if not found
 */
export async function geocodeLocation(locationName: string): Promise<GeocodeResult | null> {
  try {
    const params = new URLSearchParams({
      q: locationName,
      format: "json",
      limit: "1",
      addressdetails: "1",
    });

    const response = await fetch(
      `https://nominatim.openstreetmap.org/search?${params.toString()}`,
      {
        headers: {
          "User-Agent": "Atlantis-WorldNews/1.0", // Required by Nominatim
        },
      }
    );

    if (!response.ok) {
      console.error(`Geocoding error: ${response.statusText}`);
      return null;
    }

    const results = await response.json();
    
    if (!results || results.length === 0) {
      console.log(`No geocoding results found for: ${locationName}`);
      return null;
    }

    // Sort results by importance (lower is better) and use the first result
    const sortedResults = results.sort((a: any, b: any) => {
      const importanceA = a.importance || 0;
      const importanceB = b.importance || 0;
      return importanceB - importanceA; // Higher importance first
    });

    const result = sortedResults[0];
    const address = result.address || {};
    
    // Build display name from address components
    const specificParts: string[] = [];
    const addressKeys = ["place", "neighbourhood", "suburb", "city", "state", "country"];
    for (const key of addressKeys) {
      if (address[key]) {
        specificParts.push(address[key]);
      }
    }
    
    const display_name = specificParts.length > 0 
      ? specificParts.slice(0, 3).join(", ") // Use first 2-3 parts
      : result.display_name;

    return {
      lat: parseFloat(result.lat),
      lng: parseFloat(result.lon),
      display_name,
    };
  } catch (error) {
    console.error(`Error geocoding location '${locationName}':`, error);
    return null;
  }
}
