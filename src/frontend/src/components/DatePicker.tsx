/**
 * Date picker component for selecting event date.
 */

import { DatePickerInput } from "@mantine/dates";
import dayjs from "dayjs";

interface DatePickerProps {
  value: string; // YYYY-MM-DD format
  onChange: (date: string) => void;
}

export function DatePicker({ value, onChange }: DatePickerProps) {
  const date = value ? dayjs(value).toDate() : null;

  const handleChange = (date: Date | null) => {
    if (date) {
      const formatted = dayjs(date).format("YYYY-MM-DD");
      onChange(formatted);
    }
  };

  return (
    <DatePickerInput
      value={date}
      onChange={handleChange}
      maxDate={new Date()}
      placeholder="Select date"
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

