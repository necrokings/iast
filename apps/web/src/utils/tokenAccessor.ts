// ============================================================================
// Token Accessor - Provides access to MSAL tokens outside React context
// ============================================================================

/**
 * Type for the token accessor function
 */
type TokenAccessor = () => Promise<string | null>;

/**
 * Stored token accessor function - set by useAuth hook
 */
let tokenAccessor: TokenAccessor | null = null;

/**
 * Set the token accessor function (called from useAuth hook)
 */
export function setTokenAccessor(accessor: TokenAccessor): void {
  tokenAccessor = accessor;
}

/**
 * Clear the token accessor (called on logout)
 */
export function clearTokenAccessor(): void {
  tokenAccessor = null;
}

/**
 * Get the current access token
 * Can be called from anywhere (services, WebSocket handlers, etc.)
 */
export async function getAccessToken(): Promise<string | null> {
  if (!tokenAccessor) {
    console.warn('Token accessor not initialized - user may not be authenticated');
    return null;
  }
  return tokenAccessor();
}
