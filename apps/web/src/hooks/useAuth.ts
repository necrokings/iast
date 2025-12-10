// ============================================================================
// useAuth Hook - MSAL Authentication State Management
// ============================================================================

import { useState, useEffect, useCallback } from 'react';
import { useMsal, useAccount } from '@azure/msal-react';
import { InteractionStatus, InteractionRequiredAuthError } from '@azure/msal-browser';
import { apiConfig, loginRequest } from '../config/authConfig';
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
  getApiAccessToken: () => Promise<string | null>;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

export function useAuth(): UseAuthReturn {
  const { instance, accounts, inProgress } = useMsal();
  const account = useAccount(accounts[0] || null);
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Extract user info from account
  useEffect(() => {
    if (account) {
      setUserInfo({
        id: account.localAccountId,
        name: account.name || '',
        email: account.username || '',
        username: account.username || '',
      });
      setIsAuthenticated(true);
    } else {
      setUserInfo(null);
      setIsAuthenticated(false);
    }
  }, [account]);

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

  // Set up token accessor for services to use
  useEffect(() => {
    if (isAuthenticated && account) {
      setTokenAccessor(getApiAccessToken);
    } else {
      clearTokenAccessor();
    }
  }, [isAuthenticated, account, getApiAccessToken]);

  /**
   * Login user
   */
  const login = useCallback(async () => {
    try {
      await instance.loginRedirect(loginRequest);
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
      setUserInfo(null);
      setIsAuthenticated(false);
    } catch (error) {
      console.error('Logout failed:', error);
    }
  }, [instance, account]);

  // Set loading to false once MSAL has finished initialization
  useEffect(() => {
    if (inProgress === InteractionStatus.None) {
      setIsLoading(false);
    }
  }, [inProgress]);

  return {
    isAuthenticated,
    isLoading,
    userInfo,
    getApiAccessToken,
    login,
    logout,
  };
}
