/**
 * Map style picker component for switching between map styles.
 */

import React from "react";

export type MapStyle =
  | "mapbox://styles/mapbox/light-v11"
  | "mapbox://styles/mapbox/dark-v11"
  | "mapbox://styles/mapbox/streets-v12"
  | "mapbox://styles/mapbox/satellite-v9"
  | "mapbox://styles/mapbox/satellite-streets-v12"
  | "mapbox://styles/mapbox/outdoors-v12";

interface MapStylePickerProps {
  value: MapStyle;
  onChange: (style: MapStyle) => void;
}

const mapStyles: { value: MapStyle; label: string; icon: string }[] = [
  { value: "mapbox://styles/mapbox/light-v11", label: "Light", icon: "☀️" },
  { value: "mapbox://styles/mapbox/dark-v11", label: "Dark", icon: "🌙" },
  { value: "mapbox://styles/mapbox/streets-v12", label: "Streets", icon: "🗺️" },
  { value: "mapbox://styles/mapbox/satellite-v9", label: "Satellite", icon: "🛰️" },
  { value: "mapbox://styles/mapbox/satellite-streets-v12", label: "Satellite + Streets", icon: "🛰️🗺️" },
  { value: "mapbox://styles/mapbox/outdoors-v12", label: "Outdoors", icon: "🏔️" },
];

export function MapStylePicker({ value, onChange }: MapStylePickerProps) {
  return (
    <div className="map-style-picker">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as MapStyle)}
        className="map-style-select"
        title="Map Style"
      >
        {mapStyles.map((style) => (
          <option key={style.value} value={style.value}>
            {style.icon} {style.label}
          </option>
        ))}
      </select>
    </div>
  );
}

