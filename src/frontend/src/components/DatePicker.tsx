/**
 * Date picker component for selecting event date.
 */

import React from "react";
import DatePickerLib from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

interface DatePickerProps {
  value: string; // YYYY-MM-DD format
  onChange: (date: string) => void;
}

export function DatePicker({ value, onChange }: DatePickerProps) {
  const date = value ? new Date(value) : new Date();

  const handleChange = (date: Date | null) => {
    if (date) {
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      onChange(`${year}-${month}-${day}`);
    }
  };

  return (
    <DatePickerLib
      selected={date}
      onChange={handleChange}
      dateFormat="yyyy-MM-dd"
      maxDate={new Date()}
      className="date-picker"
    />
  );
}

