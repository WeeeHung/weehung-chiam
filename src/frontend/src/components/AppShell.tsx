/**
 * App shell component - top bar with navigation, title, language, and date picker.
 */

import { Group, Title, ActionIcon } from "@mantine/core";
import { DatePicker } from "./DatePicker";
import { LanguagePicker } from "./LanguagePicker";
import { MapStylePicker, MapStyle } from "./MapStylePicker";

interface AppShellProps {
  date: string;
  language: string;
  mapStyle: MapStyle;
  onDateChange: (date: string) => void;
  onLanguageChange: (language: string) => void;
  onMapStyleChange: (style: MapStyle) => void;
}

export function AppShell({
  date,
  language,
  mapStyle,
  onDateChange,
  onLanguageChange,
  onMapStyleChange,
}: AppShellProps) {
  return (
    <Group className="app-shell" justify="space-between" align="center" p="md">
      <Group gap="xs">
        <ActionIcon variant="subtle" size="lg" title="Explore">
          <span>🔍</span>
        </ActionIcon>
        <ActionIcon variant="subtle" size="lg" title="Time Travel">
          <span>🕐</span>
        </ActionIcon>
        <ActionIcon variant="subtle" size="lg" title="Profile">
          <span>👤</span>
        </ActionIcon>
      </Group>
      
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
          <DatePicker value={date} onChange={onDateChange} />
        </div>
      </Group>
    </Group>
  );
}

