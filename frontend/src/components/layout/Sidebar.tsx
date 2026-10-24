import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquare,
  FileText,
  Settings,
  LogOut,
  Layers,
  X,
  User as UserIcon,
} from "lucide-react";
import { useAuth } from "../../hooks/useAuth";
import ThemeToggle from "../common/ThemeToggle";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const navItems = [
    { name: "Dashboard", path: "/dashboard", icon: LayoutDashboard },
    { name: "Ask Cogniva", path: "/chat", icon: MessageSquare },
    { name: "Documents", path: "/documents", icon: FileText },
  ];

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 lg:hidden transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Sidebar container */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-[#252B27] dark:bg-[#121614] text-[#F4F5F2] border-r border-[#39433C] flex flex-col transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          isOpen ? "translate-x-0 shadow-xl" : "-translate-x-full"
        }`}
      >
        {/* Brand / Logo Header */}
        <div className="h-16 px-5 border-b border-[#39433C] flex items-center justify-between">
          <NavLink to="/dashboard" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-[#267653] dark:bg-[#42B883] text-white dark:text-[#121614] flex items-center justify-center font-bold text-sm shadow-xs">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <span className="text-sm font-semibold tracking-wide uppercase text-[#F4F5F2]">
                Cogniva
              </span>
              <p className="text-[10px] text-[#C0C8C1] font-medium tracking-wider uppercase">
                Enterprise AI
              </p>
            </div>
          </NavLink>
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded text-[#C0C8C1] hover:text-[#F4F5F2] hover:bg-[#2C352F]"
            aria-label="Close navigation"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Primary Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <div className="px-3 pb-2 text-[10px] font-semibold tracking-wider text-[#88948B] uppercase">
            Workspace
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => onClose()}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-[#2C352F] text-[#42B883] font-semibold border-l-2 border-[#42B883]"
                      : "text-[#C0C8C1] hover:text-[#F4F5F2] hover:bg-[#2C352F]/70"
                  }`
                }
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span>{item.name}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Bottom User Profile & Settings Section */}
        <div className="p-3 border-t border-[#39433C] space-y-1">
          <NavLink
            to="/settings"
            onClick={() => onClose()}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                isActive
                  ? "bg-[#2C352F] text-[#42B883] font-semibold"
                  : "text-[#C0C8C1] hover:text-[#F4F5F2] hover:bg-[#2C352F]/70"
              }`
            }
          >
            <Settings className="w-4 h-4 shrink-0" />
            <span>Settings</span>
          </NavLink>

          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium text-rose-400 hover:bg-[#2C352F] hover:text-rose-300 transition-colors cursor-pointer"
          >
            <LogOut className="w-4 h-4 shrink-0" />
            <span>Log out</span>
          </button>

          {/* User profile & theme section */}
          <div className="mt-2 pt-2 border-t border-[#39433C] px-3 py-1.5 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-7 h-7 rounded-md bg-[#2C352F] border border-[#39433C] flex items-center justify-center text-[#C0C8C1] shrink-0">
                <UserIcon className="w-3.5 h-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-[#F4F5F2] truncate">
                  {user?.full_name || user?.email?.split("@")[0]}
                </p>
                <p className="text-[10px] text-[#88948B] truncate">{user?.email}</p>
              </div>
            </div>
            <ThemeToggle compact className="shrink-0 bg-[#2C352F] border-[#39433C]" />
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
