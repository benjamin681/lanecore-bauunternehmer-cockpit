"use client";

import { ButtonHTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-bauplan-600 text-white hover:bg-bauplan-700 shadow-sm focus-visible:ring-bauplan-500",
        secondary:
          "bg-white text-bauplan-700 border border-slate-200 hover:bg-slate-50 focus-visible:ring-bauplan-500",
        ghost: "text-slate-700 hover:bg-slate-100",
        danger:
          "bg-danger-500 text-white hover:bg-danger-600 shadow-sm focus-visible:ring-danger-500",
        success:
          "bg-success-500 text-white hover:bg-success-600 shadow-sm focus-visible:ring-success-500",
        accent:
          "bg-accent-500 text-white hover:bg-accent-600 shadow-sm focus-visible:ring-accent-500",
      },
      size: {
        sm: "h-8 px-3 text-sm",
        md: "h-10 px-4 text-sm",
        lg: "h-12 px-6 text-base",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";
