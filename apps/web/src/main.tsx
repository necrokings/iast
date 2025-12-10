import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { PublicClientApplication, EventType, type EventMessage, type AuthenticationResult } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import { msalConfig } from './config/authConfig'
import './index.css'

// Import the generated route tree
import { routeTree } from './routeTree.gen'

// Create MSAL instance
const msalInstance = new PublicClientApplication(msalConfig)

// Initialize MSAL
msalInstance.initialize().then(() => {
  // Handle redirect promise (for redirect-based auth flows)
  msalInstance.handleRedirectPromise().then((response) => {
    if (response) {
      msalInstance.setActiveAccount(response.account)
    }
  }).catch((error) => {
    console.error('Redirect error:', error)
  })

  // Set active account on login success
  msalInstance.addEventCallback((event: EventMessage) => {
    if (event.eventType === EventType.LOGIN_SUCCESS && event.payload) {
      const payload = event.payload as AuthenticationResult
      msalInstance.setActiveAccount(payload.account)
    }
  })

  // If there's no active account but there are accounts, set the first one
  if (!msalInstance.getActiveAccount() && msalInstance.getAllAccounts().length > 0) {
    msalInstance.setActiveAccount(msalInstance.getAllAccounts()[0])
  }

  // Create a new router instance
  const router = createRouter({ routeTree })

  // Register the router instance for type safety
  declare module '@tanstack/react-router' {
    interface Register {
      router: typeof router
    }
  }

  // Render the app
  const rootElement = document.getElementById('root')
  if (rootElement && !rootElement.innerHTML) {
    const root = createRoot(rootElement)
    root.render(
      <StrictMode>
        <MsalProvider instance={msalInstance}>
          <RouterProvider router={router} />
        </MsalProvider>
      </StrictMode>,
    )
  }
}).catch((error) => {
  console.error('MSAL initialization error:', error)
})
