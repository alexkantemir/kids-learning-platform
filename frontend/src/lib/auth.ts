'use client';

const TOKEN_KEY = 'kids_token';
const USER_KEY = 'kids_user';

export interface AuthUser {
  token: string;
  role: 'parent' | 'child';
  user_id: number;
  child_id: number | null;
}

export function saveAuth(data: AuthUser) {
  if (typeof window !== 'undefined') {
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(data));
  }
}

export function getAuth(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function clearAuth() {
  if (typeof window !== 'undefined') {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
}
