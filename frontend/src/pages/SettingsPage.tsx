import React, { useState } from "react";
import { User, Shield, Palette, CheckCircle2, Copy, Check } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import Badge from "../components/common/Badge";

export const SettingsPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<"profile" | "security" | "appearance">("profile");
  const [copiedId, setCopiedId] = useState(false);

  const handleCopyId = () => {
    if (user?.id) {
      navigator.clipboard.writeText(user.id);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Navigation tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6">
          <button
            onClick={() => setActiveTab("profile")}
            className={`py-3 px-1 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "profile"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            <User className="w-4 h-4" />
            Profile
          </button>
          <button
            onClick={() => setActiveTab("security")}
            className={`py-3 px-1 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "security"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            <Shield className="w-4 h-4" />
            Security
          </button>
          <button
            onClick={() => setActiveTab("appearance")}
            className={`py-3 px-1 text-sm font-semibold border-b-2 transition-colors flex items-center gap-2 ${
              activeTab === "appearance"
                ? "border-indigo-600 text-indigo-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            <Palette className="w-4 h-4" />
            Appearance
          </button>
        </nav>
      </div>

      {/* Profile Tab */}
      {activeTab === "profile" && (
        <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs max-w-2xl space-y-6">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              Account Profile
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Your real account details resolved from the authenticated session.
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-slate-100">
            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Full Name
              </label>
              <p className="text-sm font-medium text-slate-800">
                {user?.full_name || "Not provided"}
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Email Address
              </label>
              <p className="text-sm font-medium text-slate-800">{user?.email}</p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                User ID (UUID)
              </label>
              <div className="flex items-center gap-2">
                <code className="text-xs font-mono bg-slate-50 px-2 py-1 rounded-md border border-slate-200 text-slate-700">
                  {user?.id}
                </code>
                <button
                  onClick={handleCopyId}
                  className="p-1 rounded text-slate-400 hover:text-slate-600 transition-colors"
                  title="Copy User ID"
                >
                  {copiedId ? (
                    <Check className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="w-3.5 h-3.5" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Account Status
              </label>
              <Badge variant={user?.is_active ? "success" : "danger"} size="sm">
                {user?.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Role Privilege
              </label>
              <Badge variant={user?.is_superuser ? "purple" : "secondary"} size="sm">
                {user?.is_superuser ? "Superuser / Admin" : "Standard Member"}
              </Badge>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Created At
              </label>
              <p className="text-xs text-slate-600 font-medium">
                {user?.created_at ? new Date(user.created_at).toLocaleString() : "—"}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Security Tab */}
      {activeTab === "security" && (
        <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs max-w-2xl space-y-6">
          <div>
            <h3 className="text-base font-semibold text-slate-900">
              Security & Credentials
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Overview of active authentication safeguards.
            </p>
          </div>

          <div className="space-y-4 pt-4 border-t border-slate-100">
            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-slate-800">
                  Password Encryption
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Passwords are securely hashed with salted bcrypt rounds before persistence in PostgreSQL.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-100">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-semibold text-slate-800">
                  JWT Session Management
                </p>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Stateless JSON Web Tokens with HS256 signature verification and automated expiration enforcement.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Appearance Tab */}
      {activeTab === "appearance" && (
        <div className="bg-white border border-slate-200/90 rounded-2xl p-6 shadow-xs max-w-2xl space-y-6">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Appearance</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Workspace theme and visual preferences.
            </p>
          </div>

          <div className="pt-4 border-t border-slate-100">
            <p className="text-xs text-slate-600 leading-relaxed">
              Cogniva uses a calibrated enterprise light theme designed with subtle blue/purple accents, optimal whitespace, and rounded cards for readability.
            </p>
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
