/**
 * App shell component - top bar with navigation, title, language, and date picker.
 */

import { Group, Title, ActionIcon } from "@mantine/core";
import { DatePicker } from "./DatePicker";
import { LanguagePicker } from "./LanguagePicker";
import { MapStylePicker, MapStyle } from "./MapStylePicker";

interface AppShellProps {
  startDate: string;
  endDate: string;
  language: string;
  mapStyle: MapStyle;
  onDateChange: (startDate: string, endDate: string) => void;
  onLanguageChange: (language: string) => void;
  onMapStyleChange: (style: MapStyle) => void;
}

export function AppShell({
  startDate,
  endDate,
  language,
  mapStyle,
  onDateChange,
  onLanguageChange,
  onMapStyleChange,
}: AppShellProps) {
  return (
    <Group className="app-shell" justify="space-between" align="center" p="md">
      
      <Title order={4} fw={500} className="app-shell-title">
        Atlantis: World News / History
      </Title>
      
      <Group gap="md" align="center">
        <div className="map-style-selector">
          <MapStylePicker value={mapStyle} onChange={onMapStyleChange} />
        </div>
        <Group gap="xs" align="center" className="language-selector">
          <LanguagePicker value={language} onChange={onLanguageChange} />
        </Group>
        <div className="date-selector">
          <DatePicker 
            startDate={startDate} 
            endDate={endDate} 
            onChange={onDateChange} 
          />
        </div>
      </Group>
    </Group>
  );
}

