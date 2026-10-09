import React from "react";
import { Menu, Shield } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";

interface HeaderProps {
  title: string;
  subtitle?: string;
  onMenuClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ title, subtitle, onMenuClick }) => {
  const { user } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-4 sm:px-6 flex items-center justify-between sticky top-0 z-30">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="lg:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100 focus:outline-none"
          aria-label="Toggle navigation"
        >
          <Menu className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-lg font-bold text-slate-900 leading-tight">{title}</h1>
          {subtitle && <p className="text-xs text-slate-500 hidden sm:block">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs text-slate-600 font-medium">
          <Shield className="w-3.5 h-3.5 text-emerald-600" />
          <span className="hidden sm:inline">Authenticated as</span>
          <span className="font-semibold text-slate-800">{user?.email}</span>
        </div>
      </div>
    </header>
  );
};

export default Header;
