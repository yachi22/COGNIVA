import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Layers, Mail, Lock, AlertCircle, ArrowRight } from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import Input from "../components/common/Input";
import Button from "../components/common/Button";
import ThemeToggle from "../components/common/ThemeToggle";

export const Login: React.FC = () => {
  const { login, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/dashboard";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();
    setLocalError(null);

    if (!email.trim() || !password) {
      setLocalError("Please enter both email and password.");
      return;
    }

    try {
      await login({ email: email.trim(), password });
      navigate(from, { replace: true });
    } catch {
      // Error is handled in AuthContext
    }
  };

  const displayedError = localError || error;

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 transition-colors">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <Link to="/" className="inline-flex items-center gap-2.5 mb-3">
          <div className="w-9 h-9 rounded-md bg-[#267653] dark:bg-[#42B883] text-white dark:text-[#121614] flex items-center justify-center font-bold text-sm shadow-xs">
            <Layers className="w-4 h-4" />
          </div>
          <span className="text-xl font-bold tracking-wide uppercase text-primary">
            Cogniva
          </span>
        </Link>
        <h2 className="text-lg font-bold text-primary tracking-tight">
          Enterprise Tenant Authentication
        </h2>
        <p className="mt-1 text-xs text-secondary">
          Enter your authorized credentials to access your isolated knowledge pool
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-surface py-7 px-6 sm:px-8 border border-border rounded-xl shadow-xs transition-colors">
          {displayedError && (
            <div className="mb-4 p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-start gap-2.5 text-xs text-rose-800 dark:text-rose-200">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{displayedError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email address"
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (displayedError) clearError();
              }}
              placeholder="name@company.com"
              leftIcon={<Mail className="w-4 h-4" />}
              autoComplete="email"
              required
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (displayedError) clearError();
              }}
              placeholder="••••••••"
              leftIcon={<Lock className="w-4 h-4" />}
              autoComplete="current-password"
              required
            />

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full mt-2"
              isLoading={isLoading}
              icon={<ArrowRight className="w-4 h-4" />}
            >
              Authenticate & Sign In
            </Button>
          </form>

          <div className="mt-5 text-center text-xs text-secondary pt-5 border-t border-border flex items-center justify-between">
            <span>Don't have an account yet?</span>
            <Link
              to="/register"
              className="font-semibold text-accent hover:underline transition-colors"
            >
              Register tenant →
            </Link>
          </div>
        </div>

        <div className="mt-4 flex justify-center">
          <ThemeToggle compact />
        </div>
      </div>
    </div>
  );
};

export default Login;
