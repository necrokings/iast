// ============================================================================
// LoginASTForm Component - Form for Login AST with credential persistence
// ============================================================================

import { useCallback, useState, useMemo } from 'react';
import { Input, Checkbox, Button, Card, StatusBadge, ProgressBar, ItemResultList } from '../../components/ui';
import { useAST } from '../../hooks/useAST';
import { useAuthContext } from '../../context/AuthContext';
import { useCredentials } from '../shared';
import { parsePolicyNumbers } from './types';

export function LoginASTForm(): React.ReactNode {
  const { executeAST, status, isRunning, lastResult, progress, itemResults } = useAST();
  const { user } = useAuthContext();
  const {
    credentials,
    setUsername,
    setPassword,
    setRememberMe,
    isValid,
  } = useCredentials();

  // Policy numbers input
  const [policyInput, setPolicyInput] = useState<string>('');

  // Parse and validate policy numbers
  const { validPolicies, invalidCount } = useMemo(() => {
    const parsed = parsePolicyNumbers(policyInput);
    const parts = policyInput.split(/[,\s\n]+/).filter(Boolean);
    return {
      validPolicies: parsed,
      invalidCount: parts.length - parsed.length,
    };
  }, [policyInput]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (isValid && !isRunning) {
        const payload: Record<string, unknown> = {
          username: credentials.username,
          password: credentials.password,
          userId: user?.id || 'anonymous',
        };

        // Include policy numbers if provided
        if (validPolicies.length > 0) {
          payload.policyNumbers = validPolicies;
        }

        executeAST('login', payload);
      }
    },
    [executeAST, credentials, isValid, isRunning, validPolicies, user]
  );

  const hasPolicies = validPolicies.length > 0;

  return (
    <Card
      title="Login AST"
      description="Automated TSO login sequence"
      footer={
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <StatusBadge status={status} />
            {lastResult?.duration && !isRunning && (
              <span className="text-xs text-gray-400 dark:text-zinc-500">
                {lastResult.duration.toFixed(1)}s
              </span>
            )}
          </div>
          {lastResult?.message && !isRunning && (
            <p className="text-xs text-gray-600 dark:text-zinc-400 break-words">
              {lastResult.message}
            </p>
          )}
        </div>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Username"
            placeholder="TSO username"
            value={credentials.username}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUsername(e.target.value)}
            disabled={isRunning}
            autoComplete="username"
          />

          <Input
            label="Password"
            type="password"
            placeholder="Password"
            value={credentials.password}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
            disabled={isRunning}
            autoComplete="current-password"
          />
        </div>

        {/* Policy Numbers Textarea */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-zinc-300 mb-1">
            Policy Numbers
            {validPolicies.length > 0 && (
              <span className="ml-2 text-xs font-normal text-gray-500 dark:text-zinc-500">
                ({validPolicies.length} valid)
              </span>
            )}
          </label>
          <textarea
            className={`
              w-full px-3 py-2 text-sm font-mono
              bg-white dark:bg-zinc-900
              border border-gray-300 dark:border-zinc-700
              rounded-md shadow-sm
              text-gray-900 dark:text-zinc-100
              placeholder:text-gray-400 dark:placeholder:text-zinc-500
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500
              disabled:bg-gray-100 dark:disabled:bg-zinc-800 disabled:cursor-not-allowed
            `}
            rows={3}
            placeholder="Enter 9-char policy numbers (comma, space, or newline separated)"
            value={policyInput}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setPolicyInput(e.target.value)}
            disabled={isRunning}
          />
          {invalidCount > 0 && (
            <p className="mt-1 text-xs text-yellow-600 dark:text-yellow-400">
              {invalidCount} invalid policy number(s) will be skipped
            </p>
          )}
          <p className="mt-1 text-xs text-gray-500 dark:text-zinc-500">
            Optional. Leave empty for login-only test.
          </p>
        </div>

        <Checkbox
          label="Remember credentials"
          description="Save login info in browser"
          checked={credentials.rememberMe}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRememberMe(e.target.checked)}
          disabled={isRunning}
        />

        {/* Progress Bar (shown during batch processing) */}
        {isRunning && progress && hasPolicies && (
          <ProgressBar
            value={progress.percentage}
            label={`Processing ${progress.current} of ${progress.total}`}
            currentItem={progress.currentItem}
            variant={progress.itemStatus === 'failed' ? 'error' : 'default'}
          />
        )}

        {/* Item Results (shown during and after batch processing) */}
        {itemResults.length > 0 && (
          <ItemResultList items={itemResults} maxHeight="180px" />
        )}

        <Button
          type="submit"
          variant="primary"
          size="md"
          className="w-full"
          disabled={!isValid}
          isLoading={isRunning}
        >
          {isRunning
            ? (hasPolicies ? 'Processing...' : 'Running...')
            : (validPolicies.length > 0 ? `Run Login + ${validPolicies.length} Policies` : 'Run Login')
          }
        </Button>

        {lastResult?.error && (
          <div className="p-2 text-xs bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-red-700 dark:text-red-400">
            {lastResult.error}
          </div>
        )}
      </form>
    </Card>
  );
}
