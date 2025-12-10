// ============================================================================
// MSAL Configuration for Azure Entra ID
// ============================================================================

import { type Configuration, LogLevel, type PopupRequest } from '@azure/msal-browser';

// Get config from environment variables
const clientId = import.meta.env.VITE_ENTRA_CLIENT_ID || '';
const tenantId = import.meta.env.VITE_ENTRA_TENANT_ID || '';
const redirectUri = import.meta.env.VITE_ENTRA_REDIRECT_URI || window.location.origin;
const apiScope = import.meta.env.VITE_ENTRA_API_SCOPE || '';

/**
 * MSAL Configuration
 */
export const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
    postLogoutRedirectUri: redirectUri,
    navigateToLoginRequestUrl: true,
  },
  cache: {
    cacheLocation: 'localStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        switch (level) {
          case LogLevel.Error:
            console.error(message);
            break;
          case LogLevel.Warning:
            console.warn(message);
            break;
          case LogLevel.Info:
            // console.info(message);
            break;
          case LogLevel.Verbose:
            // console.debug(message);
            break;
        }
      },
      logLevel: LogLevel.Warning,
    },
  },
};

/**
 * Scopes for Microsoft Graph API (user profile)
 */
export const graphTokenRequest: PopupRequest = {
  scopes: ['User.Read'],
};

/**
 * Scopes for our backend API
 */
export const apiConfig = {
  scopes: apiScope ? [apiScope] : [],
};

/**
 * Login request configuration
 */
export const loginRequest: PopupRequest = {
  scopes: [...graphTokenRequest.scopes, ...apiConfig.scopes],
};
