import React, { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";

export const AppLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  // Determine current page title based on route
  const getPageInfo = () => {
    switch (location.pathname) {
      case "/dashboard":
        return { title: "Dashboard", subtitle: "Workspace overview and recent activity" };
      case "/chat":
        return { title: "Ask Cogniva", subtitle: "Ask questions about your organization's knowledge" };
      case "/documents":
        return { title: "Documents", subtitle: "Knowledge source library and document ingestion" };
      case "/settings":
        return { title: "Settings", subtitle: "Manage your account, security, and preferences" };
      default:
        return { title: "Cogniva", subtitle: "Enterprise Knowledge Platform" };
    }
  };

  const { title, subtitle } = getPageInfo();

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar navigation */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Header
          title={title}
          subtitle={subtitle}
          onMenuClick={() => setSidebarOpen(true)}
        />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-7xl mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
