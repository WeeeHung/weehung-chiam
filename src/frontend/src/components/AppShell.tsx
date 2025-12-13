/**
 * App shell component - top bar with navigation, title, language, and date picker.
 */

import React from "react";
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
    <div className="app-shell">
      <div className="app-shell-left">
        <button className="nav-button" title="Explore">
          <span>🔍</span>
        </button>
        <button className="nav-button" title="Time Travel">
          <span>🕐</span>
        </button>
        <button className="nav-button" title="Profile">
          <span>👤</span>
        </button>
      </div>
      <div className="app-shell-center">
        <h1>world news / history</h1>
      </div>
      <div className="app-shell-right">
        <div className="map-style-selector">
          <MapStylePicker value={mapStyle} onChange={onMapStyleChange} />
        </div>
        <div className="language-selector">
          <span>🌐</span>
          <LanguagePicker value={language} onChange={onLanguageChange} />
        </div>
        <div className="date-selector">
          <DatePicker value={date} onChange={onDateChange} />
        </div>
      </div>
    </div>
  );
}

