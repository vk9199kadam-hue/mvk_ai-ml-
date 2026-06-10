"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useMutation } from "convex/react";
import { api } from "../../convex/_generated/api";
import type { Doc } from "../../convex/_generated/dataModel";

type User = Doc<"users"> & { is_active: boolean };

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (email: string, password: string, name: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Simple hash for demo — in production use proper bcrypt on the server
async function simpleHash(password: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const createUser = useMutation(api.users.createUser);

  useEffect(() => {
    const storedUser = localStorage.getItem("user");
    if (storedUser) {
      try {
        setUser(JSON.parse(storedUser));
      } catch {
        localStorage.removeItem("user");
      }
    }
    setIsLoading(false);
  }, []);

  // Login: check localStorage for demo user, or look up via query
  const login = useCallback(async (email: string, password: string) => {
    // For demo: create user if doesn't exist, then "login"
    try {
      const passwordHash = await simpleHash(password);
      const result = await createUser({
        email,
        name: email.split("@")[0],
        passwordHash,
        role: "analyst",
      });
      const userData: User = {
        _id: result.userId as any,
        email: result.email,
        name: result.name,
        role: "analyst",
        createdAt: Date.now(),
        is_active: true,
      } as any;
      localStorage.setItem("user", JSON.stringify(userData));
      setUser(userData);
    } catch (err: any) {
      if (err.message?.includes("already exists")) {
        // User exists — "log in" with stored data
        const userData: User = {
          _id: "" as any,
          email,
          name: email.split("@")[0],
          role: "analyst",
          createdAt: Date.now(),
          is_active: true,
        } as any;
        localStorage.setItem("user", JSON.stringify(userData));
        setUser(userData);
      } else {
        throw err;
      }
    }
  }, [createUser]);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const passwordHash = await simpleHash(password);
    await createUser({
      email,
      name,
      passwordHash,
      role: "analyst",
    });
  }, [createUser]);

  const logout = useCallback(() => {
    localStorage.removeItem("user");
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        register,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
