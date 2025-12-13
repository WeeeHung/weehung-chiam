/**
 * Language picker component.
 */

import { Select } from "@mantine/core";

interface LanguagePickerProps {
  value: string;
  onChange: (language: string) => void;
}

const languages = [
  { value: "en", label: "English" },
  { value: "zh", label: "中文" },
  { value: "es", label: "Español" },
  { value: "fr", label: "Français" },
];

export function LanguagePicker({ value, onChange }: LanguagePickerProps) {
  return (
    <Select
      value={value}
      onChange={(val) => val && onChange(val)}
      data={languages}
      size="sm"
      radius="md"
      styles={{
        input: {
          background: "rgba(255, 255, 255, 0.6)",
          backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          border: "1px solid rgba(255, 255, 255, 0.2)",
          transition: "all 0.2s ease",
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

