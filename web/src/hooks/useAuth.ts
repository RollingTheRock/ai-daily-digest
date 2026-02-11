import { useState, useEffect, useCallback } from "react";
import { api } from "../utils/api";

interface User {
  login: string;
  avatar_url: string;
  name: string;
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const userData = await api.auth.me();
      setUser(userData);
    } catch (err) {
      setUser(null);
      if (err instanceof Error && err.message.includes("401")) {
        // Not authenticated, not an error
        setError(null);
      } else {
        setError(err instanceof Error ? err.message : "Auth check failed");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = useCallback((redirect?: string) => {
    api.auth.login(redirect);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
      setUser(null);
      window.location.href = "/";
    } catch (err) {
      console.error("Logout failed:", err);
    }
  }, []);

  return { user, loading, error, login, logout, checkAuth };
}
