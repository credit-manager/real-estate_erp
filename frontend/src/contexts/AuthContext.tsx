"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import api from "@/lib/api";

interface User {
  id: number;
  username?: string;
  email: string;
  full_name: string;
  role: string;
  permissions?: string[];
  must_change_password?: boolean;
}

interface LoginResult {
  success: boolean;
  message?: string;
  two_factor_required?: boolean;
}

interface VerifyResult {
  success: boolean;
  message?: string;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<LoginResult>;
  verify2FA: (code: string) => Promise<VerifyResult>;
  logout: () => Promise<void>;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const message = error.response?.data?.message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return fallback;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const loadUser = useCallback(async () => {
    try {
      const { data } = await api.get<{ authenticated: boolean; user?: User }>("/api/me");
      if (data.authenticated && data.user) {
        setUser(data.user);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadUser(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadUser]);

  const login = async (email: string, password: string): Promise<LoginResult> => {
    try {
      const { data } = await api.post("/login", { username: email, email, password });
      if (data.success) {
        if (data.user) setUser(data.user as User);
        else await loadUser();
        return { success: true };
      }
      if (data.requires_2fa || data.two_factor_required) {
        return { success: false, two_factor_required: true, message: data.message };
      }
      return { success: false, message: data.message };
    } catch (error: unknown) {
      return { success: false, message: apiErrorMessage(error, "Connection error") };
    }
  };

  const verify2FA = async (code: string): Promise<VerifyResult> => {
    try {
      const { data } = await api.post("/admin/security/2fa/verify", { code });
      if (data.success) {
        await loadUser();
        return { success: true };
      }
      return { success: false, message: data.message };
    } catch (error: unknown) {
      return { success: false, message: apiErrorMessage(error, "Error") };
    }
  };

  const logout = async () => {
    try {
      await api.post("/logout");
    } catch {
      // Local state is cleared even when the server is unavailable.
    }
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, verify2FA, logout, isAuthenticated: !!user }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
