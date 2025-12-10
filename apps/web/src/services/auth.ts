// ============================================================================
// Auth Service - API calls for user info
// ============================================================================

// Note: Authentication is handled by MSAL (Azure Entra ID)
// This service only provides the /auth/me endpoint for user info

import { config } from '../config';
import type { AuthUser } from '../types';
import type { ApiResponse } from '@terminal/shared';
import { getAccessToken } from '../utils/tokenAccessor';

async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${config.apiBaseUrl}${endpoint}`;
  const token = await getAccessToken();

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  const data: unknown = await response.json();
  return data as ApiResponse<T>;
}

/**
 * Get the current user info from the API.
 * The backend validates the Entra token and auto-provisions the user.
 */
export async function getCurrentUser(): Promise<ApiResponse<AuthUser>> {
  return apiRequest<AuthUser>('/auth/me');
}
