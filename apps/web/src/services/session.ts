// ============================================================================
// Session API Service
// ============================================================================

import { getApiUrl } from '../config';
import { getStoredToken } from '../utils/storage';
import type { UserSession } from '@terminal/shared';
import type { ExecutionRecord } from '../components/history/types';

async function fetchJson<T>(url: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (init.body) headers['Content-Type'] = 'application/json';

  const res = await fetch(url, { headers, ...init });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    throw new Error(txt || `Request failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function createSession(name: string): Promise<UserSession> {
  const url = getApiUrl('/sessions');
  const data = await fetchJson<{ success: boolean; data: UserSession }>(url, {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
  if (!data.success) throw new Error('Failed to create session');
  return data.data;
}

export async function getSessions(): Promise<UserSession[]> {
  const url = getApiUrl('/sessions');
  const data = await fetchJson<{ success: boolean; data: UserSession[] }>(url);
  if (!data.success) throw new Error('Failed to fetch sessions');
  return data.data;
}

export async function getSession(sessionId: string): Promise<UserSession> {
  const url = getApiUrl(`/sessions/${sessionId}`);
  const data = await fetchJson<{ success: boolean; data: UserSession }>(url);
  if (!data.success) throw new Error('Failed to fetch session');
  return data.data;
}

export async function updateSession(sessionId: string, name: string): Promise<UserSession> {
  const url = getApiUrl(`/sessions/${sessionId}`);
  const data = await fetchJson<{ success: boolean; data: UserSession }>(url, {
    method: 'PUT',
    body: JSON.stringify({ name }),
  });
  if (!data.success) throw new Error('Failed to update session');
  return data.data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  const url = getApiUrl(`/sessions/${sessionId}`);
  const data = await fetchJson<{ success: boolean; data: { message: string } }>(url, {
    method: 'DELETE',
  });
  if (!data.success) throw new Error('Failed to delete session');
}

/**
 * Get the active (running or paused) execution for a session
 */
export async function getActiveExecution(sessionId: string): Promise<ExecutionRecord | null> {
  const url = getApiUrl(`/sessions/${sessionId}/execution`);
  const data = await fetchJson<{ success: boolean; data: { execution: ExecutionRecord | null } }>(url);
  if (!data.success) throw new Error('Failed to fetch active execution');
  return data.data.execution;
}

export default { createSession, getSessions, getSession, updateSession, deleteSession, getActiveExecution };
