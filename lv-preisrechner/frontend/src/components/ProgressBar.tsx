"use client";

import { cn } from "@/lib/cn";

export function ProgressBar({
  value,
  label,
  className,
}: {
  value: number;
  label?: string;
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("space-y-1", className)}>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-bauplan-600 transition-all duration-300"
          style={{ width: `${clamped}%` }}
        />
      </div>
      {label && (
        <div className="text-xs text-slate-600 flex justify-between">
          <span>{label}</span>
          <span>{clamped}%</span>
        </div>
      )}
    </div>
  );
}
