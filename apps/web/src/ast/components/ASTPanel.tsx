// ============================================================================
// ASTPanel Component - Main panel with AST selector and dynamic form
// ============================================================================

import { useState, useCallback } from 'react';
import { ASTSelector } from './ASTSelector';
import { useASTRegistry } from '../registry';
import { Card } from '../../components/ui';

export function ASTPanel(): React.ReactNode {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { getAST } = useASTRegistry();

  const selectedAST = selectedId ? getAST(selectedId) : null;

  const handleSelect = useCallback((id: string | null) => {
    setSelectedId(id);
  }, []);

  return (
    <div className="space-y-4">
      {/* AST Selector */}
      <div>
        <label className="block text-left text-xs font-medium text-gray-700 dark:text-zinc-300 mb-1.5">
          Select Automation
        </label>
        <ASTSelector
          value={selectedId}
          onChange={handleSelect}
          placeholder="Search for an AST..."
        />
      </div>

      {/* Selected AST Form */}
      {selectedAST ? (
        <selectedAST.component />
      ) : (
        <Card
          title="No AST Selected"
          description="Choose an automation from the dropdown above"
        >
          <div className="text-center py-6">
            <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-gray-100 dark:bg-zinc-800 flex items-center justify-center">
              <svg
                className="w-6 h-6 text-gray-400 dark:text-zinc-500"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"
                />
              </svg>
            </div>
            <p className="text-sm text-gray-500 dark:text-zinc-500">
              Select an AST to view its configuration and run it
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
