// ============================================================================
// Auth Context - Provides auth state to components
// ============================================================================

import { createContext, useContext } from 'react';

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
}

export interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuthContext(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within an AuthProvider');
  }
  return context;
}
