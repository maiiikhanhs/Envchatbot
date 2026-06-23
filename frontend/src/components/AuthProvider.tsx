"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

import { loginApi, registerApi } from "@/services/api";

interface User {
  username: string;
  displayName: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  register: (username: string, password: string) => Promise<{ success: boolean; message: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  login: async () => ({ success: false, message: "" }),
  register: async () => ({ success: false, message: "" }),
  logout: () => { },
});

const STORAGE_KEY = "envchat_user";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  /* Restore session from localStorage on mount */
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setUser(JSON.parse(stored));
      }
    } catch {
      /* ignore */
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    try {
      const res = await loginApi(username, password);
      if (res.status === "success" && res.user) {
        const loggedInUser: User = {
          username: res.user.username,
          displayName: res.user.display_name,
        };
        setUser(loggedInUser);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(loggedInUser));
        return { success: true, message: res.message };
      }
      return { success: false, message: res.message || "Tên đăng nhập hoặc mật khẩu không đúng" };
    } catch {
      return { success: false, message: "Lỗi kết nối máy chủ" };
    }
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    try {
      const res = await registerApi(username, password);
      if (res.status === "success" && res.user) {
        const loggedInUser: User = {
          username: res.user.username,
          displayName: res.user.display_name,
        };
        setUser(loggedInUser);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(loggedInUser));
        return { success: true, message: res.message };
      }
      return { success: false, message: res.message || "Đăng ký thất bại" };
    } catch {
      return { success: false, message: "Lỗi kết nối máy chủ" };
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
