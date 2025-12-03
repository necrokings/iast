// ============================================================================
// Main App Component
// ============================================================================

import { useState, useMemo } from 'react';
import { useAuth } from './hooks/useAuth';
import { useTheme } from './hooks/useTheme';
import { Terminal } from './components/Terminal';
import { LoginForm } from './components/LoginForm';
import { RegisterForm } from './components/RegisterForm';
import { ThemeToggle } from './components/ThemeToggle';
import type { TerminalType } from '@terminal/shared';

type AuthView = 'login' | 'register';

function App(): React.ReactNode {
  const { state: authState, login, register, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [authView, setAuthView] = useState<AuthView>('login');

  // Read terminal type from URL query params
  const terminalType = useMemo<TerminalType>(() => {
    const params = new URLSearchParams(window.location.search);
    const type = params.get('type');
    return type === 'tn3270' ? 'tn3270' : 'pty';
  }, []);

  // Show loading spinner while checking auth
  if (authState.isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-white dark:bg-zinc-950">
        <div className="text-center">
          <div className="w-10 h-10 border-3 border-gray-300 dark:border-zinc-700 border-t-blue-500 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-500 dark:text-zinc-500">Loading...</p>
        </div>
      </div>
    );
  }

  // Show auth forms if not authenticated
  if (!authState.isAuthenticated) {
    if (authView === 'login') {
      return (
        <LoginForm
          onSubmit={login}
          onSwitchToRegister={() => setAuthView('register')}
          isLoading={authState.isLoading}
          error={authState.error}
          theme={theme}
          onToggleTheme={toggleTheme}
        />
      );
    }

    return (
      <RegisterForm
        onSubmit={register}
        onSwitchToLogin={() => setAuthView('login')}
        isLoading={authState.isLoading}
        error={authState.error}
        theme={theme}
        onToggleTheme={toggleTheme}
      />
    );
  }

  // Show terminal for authenticated users
  return (
    <div className="flex flex-col h-screen bg-white dark:bg-zinc-950 text-gray-900 dark:text-zinc-100">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-zinc-900 border-b border-gray-200 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <span className="text-lg font-semibold text-gray-900 dark:text-zinc-100">
            {terminalType === 'tn3270' ? 'TN3270 Terminal' : 'Terminal'}
          </span>
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
          <span className="text-sm text-gray-500 dark:text-zinc-500">
            {authState.user?.email}
          </span>
          <button
            onClick={() => void logout()}
            className="px-3 py-1.5 text-sm rounded transition-colors cursor-pointer
              bg-gray-200 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200
              hover:bg-gray-300 dark:hover:bg-zinc-700"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Terminal */}
      <main className={`flex-1 overflow-auto flex ${terminalType === 'tn3270' ? 'p-4 gap-4' : ''}`}>
        <Terminal terminalType={terminalType} autoConnect={true} />
        
        {/* Side panel for TN3270 */}
        {terminalType === 'tn3270' && (
          <div className="flex-1 min-w-[300px] p-4 rounded-lg border bg-white dark:bg-zinc-900 border-gray-200 dark:border-zinc-800">
            <h2 className="text-base font-semibold mb-4 text-gray-900 dark:text-zinc-100">
              3270 Controls
            </h2>
            
            {/* Function Keys */}
            <div className="mb-5">
              <h3 className="text-xs uppercase mb-2 text-gray-500 dark:text-zinc-500">
                Function Keys
              </h3>
              <div className="grid grid-cols-4 gap-1">
                {['PF1', 'PF2', 'PF3', 'PF4', 'PF5', 'PF6', 'PF7', 'PF8', 'PF9', 'PF10', 'PF11', 'PF12'].map((key) => (
                  <button
                    key={key}
                    className="py-1.5 px-2 text-xs rounded border cursor-pointer transition-colors
                      bg-gray-200 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200
                      border-gray-300 dark:border-zinc-700
                      hover:bg-gray-300 dark:hover:bg-zinc-700"
                  >
                    {key}
                  </button>
                ))}
              </div>
            </div>

            {/* Action Keys */}
            <div className="mb-5">
              <h3 className="text-xs uppercase mb-2 text-gray-500 dark:text-zinc-500">
                Actions
              </h3>
              <div className="flex flex-wrap gap-1">
                {['Enter', 'Clear', 'PA1', 'PA2', 'Attn', 'Reset'].map((key) => (
                  <button
                    key={key}
                    className="py-1.5 px-3 text-xs rounded border cursor-pointer transition-colors
                      bg-gray-200 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200
                      border-gray-300 dark:border-zinc-700
                      hover:bg-gray-300 dark:hover:bg-zinc-700"
                  >
                    {key}
                  </button>
                ))}
              </div>
            </div>

            {/* Connection Info */}
            <div className="mb-5">
              <h3 className="text-xs uppercase mb-2 text-gray-500 dark:text-zinc-500">
                Connection
              </h3>
              <div className="text-sm text-gray-600 dark:text-zinc-400 space-y-1">
                <div>Host: localhost:3270</div>
                <div>Terminal: IBM-3278-4-E</div>
                <div>Size: 80×43</div>
              </div>
            </div>

            {/* Keyboard Shortcuts */}
            <div>
              <h3 className="text-xs uppercase mb-2 text-gray-500 dark:text-zinc-500">
                Keyboard Shortcuts
              </h3>
              <div className="text-xs text-gray-600 dark:text-zinc-400 space-y-1">
                <div className="flex justify-between">
                  <span>F1-F12</span>
                  <span className="text-gray-400 dark:text-zinc-600">PF1-PF12</span>
                </div>
                <div className="flex justify-between">
                  <span>Shift+F1-F12</span>
                  <span className="text-gray-400 dark:text-zinc-600">PF13-PF24</span>
                </div>
                <div className="flex justify-between">
                  <span>Insert</span>
                  <span className="text-gray-400 dark:text-zinc-600">Clear</span>
                </div>
                <div className="flex justify-between">
                  <span>Ctrl+C</span>
                  <span className="text-gray-400 dark:text-zinc-600">Attn</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
