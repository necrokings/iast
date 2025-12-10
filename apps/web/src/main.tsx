import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { PublicClientApplication, EventType, type EventMessage, type AuthenticationResult } from '@azure/msal-browser'
import { MsalProvider } from '@azure/msal-react'
import { msalConfig } from './config/authConfig'
import './index.css'

// Import the generated route tree
import { routeTree } from './routeTree.gen'

// Create router instance
const router = createRouter({ routeTree })

// Create MSAL instance
const msalInstance = new PublicClientApplication(msalConfig)

// Initialize MSAL and wait for everything to be ready before rendering
async function initializeApp() {
  // Initialize MSAL
  await msalInstance.initialize()
  
  // Handle redirect promise (for redirect-based auth flows)
  // This MUST complete before rendering to avoid re-renders
  const response = await msalInstance.handleRedirectPromise()
  if (response) {
    msalInstance.setActiveAccount(response.account)
  }

  // Set active account on login success (for future logins)
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

  // Now render the app - MSAL is fully initialized
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
}

initializeApp().catch((error) => {
  console.error('App initialization error:', error)
})
