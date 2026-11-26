"use client";

import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-strong disabled:opacity-60",
  secondary: "border border-line bg-surface text-ink hover:bg-canvas disabled:opacity-60",
  ghost: "text-accent hover:bg-accent-soft disabled:opacity-60",
};

type Size = "md" | "sm";

const SIZES: Record<Size, string> = { md: "px-4", sm: "px-2.5 text-sm" };

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: Size }) {
  return (
    <button
      type="button"
      {...props}
      className={`inline-flex min-h-touch items-center justify-center whitespace-nowrap rounded-xl font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
    />
  );
}
