"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import api from "@/lib/api";

interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  permissions: string[];
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
      const token = localStorage.getItem("access_token");
      if (!token) {
        setLoading(false);
        return;
      }
      const { data } = await api.get<{ success: boolean; user?: User }>("/admin/security/me");
      if (data.success && data.user) {
        setUser(data.user);
      } else {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadUser(); }, 0);
    return () => window.clearTimeout(timer);
  }, [loadUser]);

  const login = async (email: string, password: string): Promise<LoginResult> => {
    try {
      const { data } = await api.post("/admin/login", { email, password });
      if (data.success) {
        if (data.tokens) {
          localStorage.setItem("access_token", data.tokens.access_token);
          localStorage.setItem("refresh_token", data.tokens.refresh_token);
        }
        if (data.user) setUser(data.user as User);
        return { success: true };
      }
      if (data.requires_2fa) {
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
        if (data.tokens) {
          localStorage.setItem("access_token", data.tokens.access_token);
          localStorage.setItem("refresh_token", data.tokens.refresh_token);
        }
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
      await api.post("/admin/logout");
    } catch {
      // Local logout remains authoritative if the server is unavailable.
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
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
