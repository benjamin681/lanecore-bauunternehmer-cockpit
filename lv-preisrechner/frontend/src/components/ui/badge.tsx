import { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type Variant = "default" | "success" | "warning" | "danger" | "info";

export function Badge({
  variant = "default",
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { variant?: Variant }) {
  const variants: Record<Variant, string> = {
    default: "bg-slate-100 text-slate-700",
    success: "bg-success-500/10 text-success-600 border border-success-500/20",
    warning: "bg-warning-500/10 text-warning-600 border border-warning-500/20",
    danger: "bg-danger-500/10 text-danger-600 border border-danger-500/20",
    info: "bg-bauplan-50 text-bauplan-700 border border-bauplan-100",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
