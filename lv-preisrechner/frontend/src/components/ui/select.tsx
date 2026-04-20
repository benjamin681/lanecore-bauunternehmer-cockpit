"use client";

import { SelectHTMLAttributes, forwardRef } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

export type SelectOption = {
  value: string;
  label: string;
  disabled?: boolean;
};

export type SelectProps = Omit<
  SelectHTMLAttributes<HTMLSelectElement>,
  "onChange" | "value"
> & {
  value?: string;
  onChange?: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
};

/** Native-Select gestylt wie Input.
 *
 * Fuer komplexere Faelle (Suche, Multi-Select, eigener Popover) spaeter eine
 * separate Combobox-Komponente. Fuer MVP reicht das native Element —
 * barrierefrei, mobile-native-Picker, kein eigener State-Manager noetig.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, options, placeholder, value, onChange, disabled, ...props }, ref) => {
    return (
      <div className={cn("relative", disabled && "opacity-60")}>
        <select
          ref={ref}
          value={value ?? ""}
          onChange={(e) => onChange?.(e.target.value)}
          disabled={disabled}
          className={cn(
            "w-full h-10 pl-3 pr-9 text-sm rounded-lg bg-white border border-slate-200",
            "appearance-none cursor-pointer text-slate-900",
            "focus:outline-none focus:border-bauplan-500 focus:ring-2 focus:ring-bauplan-100",
            "disabled:bg-slate-50 disabled:text-slate-500 disabled:cursor-not-allowed",
            !value && placeholder && "text-slate-400",
            className,
          )}
          {...props}
        >
          {placeholder && (
            <option value="" disabled hidden>
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option
              key={opt.value}
              value={opt.value}
              disabled={opt.disabled}
              className="text-slate-900"
            >
              {opt.label}
            </option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
      </div>
    );
  },
);
Select.displayName = "Select";

export default Select;
