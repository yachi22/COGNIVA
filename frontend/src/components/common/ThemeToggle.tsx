import React from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTheme, Theme } from "../../context/ThemeContext";

interface ThemeToggleProps {
  compact?: boolean;
  className?: string;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({ compact = false, className = "" }) => {
  const { theme, setTheme } = useTheme();

  const options: { value: Theme; label: string; icon: React.FC<{ className?: string }> }[] = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ];

  if (compact) {
    return (
      <div className={`inline-flex items-center rounded-lg border border-border bg-surface p-0.5 ${className}`}>
        {options.map((opt) => {
          const Icon = opt.icon;
          const isActive = theme === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setTheme(opt.value)}
              title={`${opt.label} mode`}
              aria-label={`${opt.label} mode`}
              className={`p-1.5 rounded-md text-xs transition-colors cursor-pointer ${
                isActive
                  ? "bg-panel text-primary font-medium shadow-xs"
                  : "text-secondary hover:text-primary hover:bg-panel/50"
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center rounded-lg border border-border bg-surface p-1 ${className}`}>
      {options.map((opt) => {
        const Icon = opt.icon;
        const isActive = theme === opt.value;
        return (
          <button
            key={opt.value}
            onClick={() => setTheme(opt.value)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors cursor-pointer ${
              isActive
                ? "bg-panel text-primary font-medium shadow-xs"
                : "text-secondary hover:text-primary hover:bg-panel/50"
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            <span>{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
};

export default ThemeToggle;
