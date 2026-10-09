import apiClient from "./api";
import { User, LoginCredentials, RegisterData, TokenResponse } from "../types/auth";

export const authService = {
  /**
   * Register a new user account.
   */
  async register(data: RegisterData): Promise<User> {
    const response = await apiClient.post<User>("/auth/register", data);
    return response.data;
  },

  /**
   * Authenticate with email and password to receive a JWT access token.
   */
  async login(credentials: LoginCredentials): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>("/auth/login", credentials);
    return response.data;
  },

  /**
   * Retrieve the currently authenticated user's profile using the stored Bearer token.
   */
  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>("/auth/me");
    return response.data;
  },

  /**
   * Logout the user by removing local tokens.
   */
  logout(): void {
    localStorage.removeItem("cogniva_token");
  },
};

export default authService;
