/**
 * Language picker component.
 */

import React from "react";

interface LanguagePickerProps {
  value: string;
  onChange: (language: string) => void;
}

const languages = [
  { code: "en", name: "English" },
  { code: "zh", name: "中文" },
  { code: "es", name: "Español" },
  { code: "fr", name: "Français" },
];

export function LanguagePicker({ value, onChange }: LanguagePickerProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="language-picker"
    >
      {languages.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.name}
        </option>
      ))}
    </select>
  );
}

