import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { api } from "../api/client";
import type { AppRole } from "../types";

interface AuthState {
  token: string;
  role: AppRole;
  employeeId: string;
}

interface AuthContextValue {
  token: string | null;
  role: AppRole | null;
  employeeId: string;
  isAuthenticated: boolean;
  login: (role: AppRole, password: string, employeeId?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  token: null,
  role: null,
  employeeId: "",
  isAuthenticated: false,
  login: async () => {},
  logout: () => {},
});

const STORAGE_KEY = "hr_ops_auth";

function loadAuth(): AuthState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveAuth(state: AuthState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function clearAuth() {
  localStorage.removeItem(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<AuthState | null>(loadAuth);

  const login = async (role: AppRole, password: string, employeeId = "") => {
    const res = await api.auth.login(role, password, employeeId);
    const state: AuthState = {
      token: res.data.token,
      role: res.data.role as AppRole,
      employeeId: res.data.employee_id,
    };
    saveAuth(state);
    setAuth(state);
  };

  const logout = () => {
    clearAuth();
    setAuth(null);
  };

  return (
    <AuthContext.Provider
      value={{
        token: auth?.token ?? null,
        role: auth?.role ?? null,
        employeeId: auth?.employeeId ?? "",
        isAuthenticated: auth !== null,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
