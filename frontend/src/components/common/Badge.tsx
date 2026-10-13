import React from "react";

export interface BadgeProps {
  children: React.ReactNode;
  variant?: "primary" | "secondary" | "success" | "warning" | "danger" | "purple" | "info" | "neutral";
  size?: "xs" | "sm" | "md";
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = "primary",
  size = "md",
  className = "",
}) => {
  const sizeStyles = {
    xs: "px-1.5 py-0.2 text-[10px]",
    sm: "px-2 py-0.5 text-[11px]",
    md: "px-2.5 py-1 text-xs",
  };

  const variantStyles = {
    primary:
      "bg-accent-subtle/40 text-[#1E5D42] dark:text-[#42B883] border-[#267653]/30 dark:border-[#42B883]/30",
    purple:
      "bg-purple-100/70 dark:bg-purple-950/40 text-purple-900 dark:text-purple-300 border-purple-300 dark:border-purple-800",
    info:
      "bg-sky-100/70 dark:bg-sky-950/40 text-sky-900 dark:text-sky-300 border-sky-300 dark:border-sky-800",
    secondary:
      "bg-panel text-secondary border-border",
    neutral:
      "bg-surface text-secondary border-border",
    success:
      "bg-emerald-100/70 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800",
    warning:
      "bg-amber-100/70 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 border-amber-300 dark:border-amber-800",
    danger:
      "bg-rose-100/70 dark:bg-rose-950/40 text-rose-900 dark:text-rose-300 border-rose-300 dark:border-rose-800",
  };

  return (
    <span
      className={`inline-flex items-center font-medium rounded-md border ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
};

export default Badge;
