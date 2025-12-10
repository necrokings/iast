// ============================================================================
// Auth Service - Azure Entra ID Token Validation using jose
// ============================================================================

import * as jose from 'jose';
import { config } from '../config';
import { TerminalError, ERROR_CODES } from '@terminal/shared';

// Azure AD token payload claims
export interface EntraTokenPayload {
  aud: string;           // Audience (API client ID)
  iss: string;           // Issuer (Azure AD tenant)
  iat: number;           // Issued at
  exp: number;           // Expiration
  sub: string;           // Subject (unique per app)
  oid: string;           // Object ID (unique across Azure AD)
  preferred_username?: string;  // User's email/UPN
  name?: string;         // Display name
  email?: string;        // Email (if available)
}

// Cached JWKS
let jwksCache: jose.JWTVerifyGetKey | null = null;
let jwksCacheTime = 0;
const JWKS_CACHE_TTL = 60 * 60 * 1000; // 1 hour

/**
 * Get or create cached JWKS for Azure AD token validation
 * Note: If behind a corporate proxy, set HTTPS_PROXY or HTTP_PROXY environment variable
 */
async function getJWKS(): Promise<jose.JWTVerifyGetKey> {
  const now = Date.now();
  
  if (jwksCache && (now - jwksCacheTime) < JWKS_CACHE_TTL) {
    return jwksCache;
  }

  // Use common endpoint which works for multi-tenant apps
  const jwksUri = `https://login.microsoftonline.com/common/discovery/v2.0/keys`;
  
  console.log(`Fetching JWKS from: ${jwksUri}`);
  
  jwksCache = jose.createRemoteJWKSet(new URL(jwksUri));
  jwksCacheTime = now;
  
  return jwksCache;
}

/**
 * Verify an Azure Entra ID access token
 * Returns the validated payload with user claims
 */
export async function verifyEntraToken(token: string): Promise<EntraTokenPayload> {
  try {
    const jwks = await getJWKS();
    
    // Accept both api://clientId and clientId as valid audiences
    const configuredAudience = config.auth.entraAudience;
    const audiences = [
      configuredAudience,
      configuredAudience.replace('api://', ''),
      `api://${configuredAudience}`,
    ].filter((v, i, a) => a.indexOf(v) === i); // unique values
    
    const { payload } = await jose.jwtVerify(token, jwks, {
      audience: audiences,
      issuer: `https://login.microsoftonline.com/${config.auth.entraTenantId}/v2.0`,
    });

    // Validate required claims
    if (!payload.oid || typeof payload.oid !== 'string') {
      throw new Error('Missing oid claim');
    }

    return {
      aud: payload.aud as string,
      iss: payload.iss as string,
      iat: payload.iat as number,
      exp: payload.exp as number,
      sub: payload.sub as string,
      oid: payload.oid as string,
      preferred_username: payload.preferred_username as string | undefined,
      name: payload.name as string | undefined,
      email: (payload.email || payload.preferred_username) as string | undefined,
    };
  } catch (error) {
    if (error instanceof jose.errors.JWTExpired) {
      throw TerminalError.fromCode(ERROR_CODES.AUTH_TOKEN_EXPIRED);
    }
    if (error instanceof jose.errors.JWTClaimValidationFailed) {
      throw TerminalError.fromCode(ERROR_CODES.AUTH_INVALID_TOKEN);
    }
    if (error instanceof jose.errors.JWSSignatureVerificationFailed) {
      throw TerminalError.fromCode(ERROR_CODES.AUTH_INVALID_TOKEN);
    }
    
    console.error('Token verification error:', error);
    throw TerminalError.fromCode(ERROR_CODES.AUTH_INVALID_TOKEN);
  }
}

/**
 * Verify token and return standardized payload for backward compatibility
 * This matches the old AuthTokenPayload interface shape
 */
export async function verifyToken(token: string): Promise<{ sub: string; email: string; iat: number; exp: number }> {
  const entraPayload = await verifyEntraToken(token);
  
  return {
    sub: entraPayload.oid, // Use oid as user ID
    email: entraPayload.email || entraPayload.preferred_username || '',
    iat: entraPayload.iat,
    exp: entraPayload.exp,
  };
}

/**
 * Extract user info from Entra token for user provisioning
 */
export function extractUserInfo(payload: EntraTokenPayload): {
  id: string;
  email: string;
  displayName: string;
} {
  return {
    id: payload.oid,
    email: payload.email || payload.preferred_username || '',
    displayName: payload.name || payload.preferred_username || 'Unknown User',
  };
}
