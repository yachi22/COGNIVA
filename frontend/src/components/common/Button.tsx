import React, { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "xs" | "sm" | "md" | "lg";
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = "primary",
  size = "md",
  isLoading = false,
  disabled = false,
  icon,
  className = "",
  ...props
}) => {
  const baseStyles =
    "inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-accent disabled:opacity-50 disabled:cursor-not-allowed select-none cursor-pointer";

  const sizeStyles = {
    xs: "px-2.5 py-1 text-xs gap-1.5",
    sm: "px-3 py-1.5 text-xs gap-1.5",
    md: "px-4 py-2 text-sm gap-2",
    lg: "px-5 py-2.5 text-base gap-2.5",
  };

  const variantStyles = {
    primary:
      "bg-[#267653] dark:bg-[#42B883] hover:bg-[#1E5D42] dark:hover:bg-[#36996D] text-white dark:text-[#121614] font-semibold border border-transparent shadow-xs",
    secondary:
      "bg-panel text-primary hover:bg-panel/80 border border-border",
    outline:
      "border border-border bg-surface hover:bg-panel text-primary",
    ghost:
      "text-secondary hover:text-primary hover:bg-panel/60 border border-transparent",
    danger:
      "bg-rose-700 hover:bg-rose-800 dark:bg-rose-600 dark:hover:bg-rose-700 text-white border border-transparent shadow-xs",
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin shrink-0" />
      ) : (
        icon && <span className="shrink-0">{icon}</span>
      )}
      {children && <span>{children}</span>}
    </button>
  );
};

export default Button;
