// ============================================================================
// useAuth Hook - Azure Entra ID Authentication with MSAL
// ============================================================================

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useMsal } from '@azure/msal-react';
import { InteractionStatus, InteractionRequiredAuthError } from '@azure/msal-browser';
import { graphTokenRequest, apiConfig } from '../config/authConfig';
import { setTokenAccessor, clearTokenAccessor } from '../utils/tokenAccessor';

export interface UserInfo {
  id: string;
  name: string;
  email: string;
  username: string;
}

export interface UseAuthReturn {
  isAuthenticated: boolean;
  isLoading: boolean;
  userInfo: UserInfo | null;
  accessToken: string | null;
  getAccessToken: () => Promise<string | null>;
  getApiAccessToken: () => Promise<string | null>;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const { instance, accounts, inProgress } = useMsal();
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const account = accounts[0];

  // Derive user info from account using useMemo
  const userInfo = useMemo<UserInfo | null>(() => {
    if (!account) return null;
    return {
      id: account.localAccountId,
      name: account.name || '',
      email: account.username || '',
      username: account.username || '',
    };
  }, [account]);

  const isAuthenticated = !!account;

  /**
   * Acquire Graph API access token silently (for user profile)
   * Falls back to interactive login if silent acquisition fails
   */
  const acquireToken = useCallback(async (): Promise<string | null> => {
    if (!account) {
      return null;
    }

    if (inProgress !== InteractionStatus.None) {
      return null;
    }

    try {
      // Try silent token acquisition first
      const response = await instance.acquireTokenSilent({
        ...graphTokenRequest,
        account,
      });

      setAccessToken(response.accessToken);
      return response.accessToken;
    } catch (error) {
      console.error('Token acquisition error:', error);
      if (error instanceof InteractionRequiredAuthError) {
        // Silent acquisition failed, require user interaction
        try {
          await instance.acquireTokenRedirect({
            ...graphTokenRequest,
            account,
          });
          return null; // Will redirect, so return null
        } catch (redirectError) {
          console.error('Token acquisition redirect failed:', redirectError);
          return null;
        }
      }
      return null;
    }
  }, [account, instance, inProgress]);

  /**
   * Get API access token for backend authentication
   * Uses custom API scope configured in Azure
   */
  const getApiAccessToken = useCallback(async (): Promise<string | null> => {
    if (!account) {
      console.warn('No active account! Sign in before calling an API.');
      return null;
    }

    if (inProgress !== InteractionStatus.None) {
      return null;
    }

    try {
      // Get access token silently with API scope
      const response = await instance.acquireTokenSilent({
        scopes: apiConfig.scopes,
        account: account,
      });

      return response.accessToken;
    } catch (error) {
      console.error('API token acquisition error:', error);
      if (error instanceof InteractionRequiredAuthError) {
        try {
          await instance.acquireTokenRedirect({
            scopes: apiConfig.scopes,
            account,
          });
          return null;
        } catch (redirectError) {
          console.error('API token acquisition redirect failed:', redirectError);
          return null;
        }
      }
      return null;
    }
  }, [account, instance, inProgress]);

  /**
   * Get current access token or acquire new one
   */
  const getAccessToken = useCallback(async (): Promise<string | null> => {
    if (accessToken) {
      return accessToken;
    }
    return await acquireToken();
  }, [accessToken, acquireToken]);

  /**
   * Login user
   */
  const login = useCallback(async () => {
    try {
      await instance.loginRedirect(graphTokenRequest);
    } catch (error) {
      console.error('Login failed:', error);
    }
  }, [instance]);

  /**
   * Logout user
   */
  const logout = useCallback(async () => {
    try {
      clearTokenAccessor();
      await instance.logoutRedirect({
        account,
      });
      setAccessToken(null);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  }, [instance, account]);

  // Initial token acquisition and token accessor setup
  useEffect(() => {
    let cancelled = false;

    const initialize = async () => {
      if (account && inProgress === InteractionStatus.None) {
        // Set up token accessor for services (API calls, WebSocket, etc.)
        setTokenAccessor(getApiAccessToken);
        
        if (!accessToken) {
          await acquireToken();
        }
      } else if (!account) {
        clearTokenAccessor();
      }
      
      if (!cancelled) {
        setIsLoading(false);
      }
    };

    void initialize();

    return () => {
      cancelled = true;
    };
  }, [account, accessToken, acquireToken, getApiAccessToken, inProgress]);

  return {
    isAuthenticated,
    isLoading,
    userInfo,
    accessToken,
    getAccessToken,
    getApiAccessToken,
    login,
    logout,
  };
}
