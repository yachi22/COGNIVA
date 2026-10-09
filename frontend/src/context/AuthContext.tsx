import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import authService from "../services/authService";
import { User, LoginCredentials, RegisterData, AuthContextType } from "../types/auth";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("cogniva_token"));
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const logout = useCallback(() => {
    authService.logout();
    setToken(null);
    setUser(null);
    setError(null);
  }, []);

  // Initialize auth state by fetching current user if token exists
  useEffect(() => {
    let isMounted = true;

    const initializeAuth = async () => {
      const storedToken = localStorage.getItem("cogniva_token");
      if (!storedToken) {
        if (isMounted) {
          setIsLoading(false);
          setUser(null);
        }
        return;
      }

      try {
        const currentUser = await authService.getCurrentUser();
        if (isMounted) {
          setUser(currentUser);
          setToken(storedToken);
        }
      } catch (err: unknown) {
        // If token is invalid or expired, clear it
        console.warn("Failed to restore session from token:", err);
        authService.logout();
        if (isMounted) {
          setUser(null);
          setToken(null);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    initializeAuth();

    // Listen for unauthorized events emitted by apiClient response interceptor
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener("cogniva:unauthorized", handleUnauthorized);

    return () => {
      isMounted = false;
      window.removeEventListener("cogniva:unauthorized", handleUnauthorized);
    };
  }, [logout]);

  const login = async (credentials: LoginCredentials): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const tokenResponse = await authService.login(credentials);
      localStorage.setItem("cogniva_token", tokenResponse.access_token);
      setToken(tokenResponse.access_token);

      // Immediately fetch authenticated user profile
      const userProfile = await authService.getCurrentUser();
      setUser(userProfile);
    } catch (err: unknown) {
      let message = "Invalid email or password. Please try again.";
      if (err && typeof err === "object" && "response" in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } };
        if (axiosError.response?.data?.detail) {
          message = axiosError.response.data.detail;
        }
      }
      setError(message);
      throw new Error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: RegisterData): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      await authService.register(data);
      // Auto-login after successful registration
      await login({ email: data.email, password: data.password });
    } catch (err: unknown) {
      let message = "Registration failed. Please try again.";
      if (err && typeof err === "object" && "response" in err) {
        const axiosError = err as { response?: { data?: { detail?: string } } };
        if (axiosError.response?.data?.detail) {
          message = axiosError.response.data.detail;
        }
      }
      setError(message);
      setIsLoading(false);
      throw new Error(message);
    }
  };

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    register,
    logout,
    error,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export default AuthContext;
