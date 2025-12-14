/**
 * Map style picker component for switching between map styles.
 */

import { Select } from "@mantine/core";

export type MapStyle =
  | "mapbox://styles/mapbox/light-v11"
  | "mapbox://styles/mapbox/dark-v11"
  | "mapbox://styles/mapbox/streets-v12"
  | "mapbox://styles/mapbox/satellite-v9"
  | "mapbox://styles/mapbox/satellite-streets-v12"
  | "mapbox://styles/mapbox/outdoors-v12"
  | "mapbox://styles/mapbox/standard";

interface MapStylePickerProps {
  value: MapStyle;
  onChange: (style: MapStyle) => void;
}

const mapStyles = [
  { value: "mapbox://styles/mapbox/light-v11", label: "☀️ Light" },
  { value: "mapbox://styles/mapbox/dark-v11", label: "🌙 Dark" },
  { value: "mapbox://styles/mapbox/streets-v12", label: "🗺️ Streets" },
  { value: "mapbox://styles/mapbox/satellite-v9", label: "🛰️ Satellite" },
  { value: "mapbox://styles/mapbox/satellite-streets-v12", label: "🛰️🗺️ Satellite + Streets" },
  { value: "mapbox://styles/mapbox/outdoors-v12", label: "🏔️ Outdoors" },
  { value: "mapbox://styles/mapbox/standard", label: "🌐 Standard" },
] as const;

export function MapStylePicker({ value, onChange }: MapStylePickerProps) {
  return (
    <Select
      value={value}
      onChange={(val) => val && onChange(val as MapStyle)}
      data={mapStyles}
      size="sm"
      radius="md"
      styles={{
        input: {
          background: "rgba(255, 255, 255, 0.6)",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          border: "1px solid rgba(255, 255, 255, 0.2)",
          transition: "all 0.2s ease",
          minWidth: "150px",
          "&:hover": {
            background: "rgba(255, 255, 255, 0.8)",
            borderColor: "rgba(255, 255, 255, 0.4)",
          },
          "&:focus": {
            background: "rgba(255, 255, 255, 0.9)",
            borderColor: "rgba(59, 130, 246, 0.5)",
          },
        },
      }}
    />
  );
}

