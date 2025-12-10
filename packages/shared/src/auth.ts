// ============================================================================
// Auth Types
// ============================================================================

export interface User {
  id: string;
  email: string;
  displayName?: string;
  createdAt: number;
  updatedAt: number;
}

export interface UserSession {
  id: string;
  userId: string;
  name: string;
  createdAt: number;
  updatedAt: number;
}

export interface AuthTokenPayload {
  sub: string; // userId (oid from Entra)
  email: string;
  iat: number;
  exp: number;
}

// ============================================================================
// Validation
// ============================================================================

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmail(email: string): boolean {
  return EMAIL_REGEX.test(email);
}
