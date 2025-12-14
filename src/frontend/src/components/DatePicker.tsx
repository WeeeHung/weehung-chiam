/**
 * Date picker component for selecting date range.
 */

import { DatePickerInput, DatesRangeValue } from "@mantine/dates";
import dayjs from "dayjs";
import { Group } from "@mantine/core";

interface DatePickerProps {
  startDate: string; // YYYY-MM-DD format
  endDate: string; // YYYY-MM-DD format
  onChange: (startDate: string, endDate: string) => void;
}

export function DatePicker({ startDate, endDate, onChange }: DatePickerProps) {
  const start = startDate ? dayjs(startDate).toDate() : null;
  const end = endDate ? dayjs(endDate).toDate() : null;
  const range: DatesRangeValue | undefined = start && end ? [start, end] : undefined;

  const handleChange = (range: DatesRangeValue) => {
    if (range && range[0] && range[1]) {
      const formattedStart = dayjs(range[0]).format("YYYY-MM-DD");
      const formattedEnd = dayjs(range[1]).format("YYYY-MM-DD");
      onChange(formattedStart, formattedEnd);
    } else if (range && range[0]) {
      // If only start date is selected, set end date to the same day
      const formatted = dayjs(range[0]).format("YYYY-MM-DD");
      onChange(formatted, formatted);
    }
  };


  return (
    <Group gap="xs" align="center">
      <DatePickerInput
        type="range"
        value={range}
        onChange={handleChange}
        maxDate={new Date()}
        placeholder="Select date range"
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
    </Group>
  );
}

