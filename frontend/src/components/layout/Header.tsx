import React from "react";
import { Menu, Shield } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import ThemeToggle from "../common/ThemeToggle";

interface HeaderProps {
  title: string;
  subtitle?: string;
  onMenuClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle, onMenuClick }) => {
  const { user } = useAuth();

  return (
    <header className="h-16 bg-surface border-b border-border px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30 transition-colors">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-1.5 rounded-md text-secondary hover:text-primary hover:bg-panel cursor-pointer"
          aria-label="Toggle navigation"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-base sm:text-lg font-semibold text-primary leading-tight">{title}</h1>
          {subtitle && <p className="text-xs text-secondary hidden sm:block">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-2.5 sm:gap-4">
        {/* Compact Theme Selector */}
        <ThemeToggle compact />

        {/* Tenant identifier chip */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-md bg-panel border border-border text-xs text-secondary font-medium">
          <Shield className="w-3.5 h-3.5 text-accent shrink-0" />
          <span className="hidden md:inline">Tenant:</span>
          <span className="font-medium text-primary truncate max-w-[140px] sm:max-w-[220px]">
            {user?.email}
          </span>
        </div>
      </div>
    </header>
  );
};

export default Header;
