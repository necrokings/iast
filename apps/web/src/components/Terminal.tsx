// ============================================================================
// Terminal Component - TN3270 Terminal
// ============================================================================

import { useEffect, useState, useRef } from 'react';
import { useTerminal } from '../hooks/useTerminal';
import { useAST } from '../hooks/useAST';
import { Pause, Play } from 'lucide-react';
import { Tooltip } from './ui';
import type { ConnectionStatus } from '../types';
import type { ASTStatusMeta, ASTProgressMeta, ASTItemResultMeta } from '@terminal/shared';
import '@xterm/xterm/css/xterm.css';

interface TerminalApi {
  runAST: (astName: string, params?: Record<string, unknown>) => void;
}

interface TerminalProps {
  sessionId?: string;
  autoConnect?: boolean;
  onStatusChange?: (status: ConnectionStatus) => void;
  onReady?: (api: TerminalApi) => void;
  onASTStatus?: (status: ASTStatusMeta) => void;
  onASTProgress?: (progress: ASTProgressMeta) => void;
  onASTItemResult?: (itemResult: ASTItemResultMeta) => void;
  onASTPaused?: (isPaused: boolean) => void;
}

// PF and PA key definitions
const PF_KEYS = [
  { label: 'PF1', key: '\x1bOP' },
  { label: 'PF2', key: '\x1bOQ' },
  { label: 'PF3', key: '\x1bOR' },
  { label: 'PF4', key: '\x1bOS' },
  { label: 'PF5', key: '\x1b[15~' },
  { label: 'PF6', key: '\x1b[17~' },
  { label: 'PF7', key: '\x1b[18~' },
  { label: 'PF8', key: '\x1b[19~' },
  { label: 'PF9', key: '\x1b[20~' },
  { label: 'PF10', key: '\x1b[21~' },
  { label: 'PF11', key: '\x1b[23~' },
  { label: 'PF12', key: '\x1b[24~' },
  { label: 'PF13', key: '\x1b[1;2P' },
  { label: 'PF14', key: '\x1b[1;2Q' },
  { label: 'PF15', key: '\x1b[1;2R' },
  { label: 'PF16', key: '\x1b[1;2S' },
  { label: 'PF17', key: '\x1b[15;2~' },
  { label: 'PF18', key: '\x1b[17;2~' },
  { label: 'PF19', key: '\x1b[18;2~' },
  { label: 'PF20', key: '\x1b[19;2~' },
  { label: 'PF21', key: '\x1b[20;2~' },
  { label: 'PF22', key: '\x1b[21;2~' },
  { label: 'PF23', key: '\x1b[23;2~' },
  { label: 'PF24', key: '\x1b[24;2~' },
];

const PA_KEYS = [
  { label: 'PA1', key: '\x1b[1;5P' },
  { label: 'PA2', key: '\x1b[1;5Q' },
  { label: 'PA3', key: '\x1b[1;5R' },
  { label: 'Clear', key: '\x1b[2~' },
  { label: 'Attn', key: '\x03' },
  { label: 'Enter', key: '\r' },
];

// Keyboard shortcuts for 3270 emulation
const KEYBOARD_SHORTCUTS = [
  { keys: 'F1-F12', action: 'PF1-PF12' },
  { keys: 'Shift+F1-F12', action: 'PF13-PF24' },
  { keys: 'Ctrl+F1', action: 'PA1' },
  { keys: 'Ctrl+F2', action: 'PA2' },
  { keys: 'Ctrl+F3', action: 'PA3' },
  { keys: 'Enter', action: 'Enter/Submit' },
  { keys: 'Tab', action: 'Next Field' },
  { keys: 'Shift+Tab', action: 'Previous Field' },
  { keys: 'Insert', action: 'Clear Screen' },
  { keys: 'Ctrl+C', action: 'Attention' },
  { keys: 'Home', action: 'Field Start' },
  { keys: 'End', action: 'Field End' },
  { keys: 'Delete', action: 'Delete Char' },
  { keys: 'Backspace', action: 'Backspace' },
];

function getStatusColor(status: ConnectionStatus): string {
  switch (status) {
    case 'connected':
      return '#0dbc79';
    case 'connecting':
    case 'reconnecting':
      return '#e5e510';
    case 'error':
      return '#cd3131';
    case 'disconnected':
    default:
      return '#666666';
  }
}

function getStatusText(status: ConnectionStatus): string {
  switch (status) {
    case 'connected':
      return 'Connected';
    case 'connecting':
      return 'Connecting...';
    case 'reconnecting':
      return 'Reconnecting...';
    case 'error':
      return 'Error';
    case 'disconnected':
    default:
      return 'Disconnected';
  }
}

export function Terminal({ sessionId, autoConnect = true, onStatusChange, onReady, onASTStatus, onASTProgress, onASTItemResult, onASTPaused }: TerminalProps): React.ReactNode {
  // Get AST running state from context first (need for inputDisabled)
  const { isRunning: isASTRunning, runningAST, status: astStatus } = useAST();
  const isPaused = astStatus === 'paused';

  const {
    terminalRef,
    status,
    sessionId: activeSessionId,
    cursorPosition,
    connect,
    disconnect,
    focus,
    sendKey,
    runAST,
    pauseAST,
    resumeAST,
    cancelAST,
  } = useTerminal({
    sessionId,
    autoConnect,
    inputDisabled: isASTRunning && !isPaused,
    onASTStatus,
    onASTProgress,
    onASTItemResult,
    onASTPaused,
  });

  // Expose API to parent
  useEffect(() => {
    onReady?.({ runAST });
  }, [onReady, runAST]);

  const [keyMenuOpen, setKeyMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    onStatusChange?.(status);
  }, [status, onStatusChange]);

  useEffect(() => {
    // Focus terminal on mount
    focus();
  }, [focus]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setKeyMenuOpen(false);
      }
    };
    if (keyMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [keyMenuOpen]);

  const handleKeyClick = (key: string) => {
    sendKey(key);
    setKeyMenuOpen(false);
    focus();
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950 w-fit">
      {/* Status bar */}
      <div className="flex items-center justify-between px-3 py-2 bg-zinc-900 border-b border-zinc-800 text-xs font-sans">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: getStatusColor(status) }}
            />
            <span className="text-zinc-100 font-medium">{getStatusText(status)}</span>
          </div>

          {/* PF/PA Keys Dropdown */}
          {status === 'connected' && (
            <div ref={menuRef} className="relative">
              <button
                onClick={() => setKeyMenuOpen(!keyMenuOpen)}
                className={`px-3 py-1.5 text-xs flex items-center gap-1 rounded border cursor-pointer transition-colors
                  ${keyMenuOpen
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-gray-100 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200 border-gray-300 dark:border-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-700'}`}
              >
                Keys ▾
              </button>

              {keyMenuOpen && (
                <div className="absolute top-full left-0 mt-1 min-w-[340px] p-3 rounded-md border shadow-lg z-50 bg-white dark:bg-zinc-900 border-gray-200 dark:border-zinc-700">
                  {/* PF Keys */}
                  <div className="mb-3">
                    <div className="text-[11px] uppercase mb-1.5 text-gray-500 dark:text-zinc-500 font-medium">
                      Function Keys
                    </div>
                    <div className="grid grid-cols-6 gap-1">
                      {PF_KEYS.map(({ label, key }) => (
                        <button
                          key={label}
                          onClick={() => handleKeyClick(key)}
                          className="px-1.5 py-1.5 text-[11px] rounded border cursor-pointer transition-colors
                            bg-gray-100 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200 
                            border-gray-300 dark:border-zinc-700
                            hover:bg-gray-200 dark:hover:bg-zinc-700 hover:border-gray-400 dark:hover:border-zinc-600
                            active:bg-gray-300 dark:active:bg-zinc-600"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* PA Keys & Actions */}
                  <div className="mb-3">
                    <div className="text-[11px] uppercase mb-1.5 text-gray-500 dark:text-zinc-500 font-medium">
                      Program Attention & Actions
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {PA_KEYS.map(({ label, key }) => (
                        <button
                          key={label}
                          onClick={() => handleKeyClick(key)}
                          className={`px-2.5 py-1.5 text-[11px] rounded border cursor-pointer transition-colors
                            ${label === 'Enter'
                              ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700 active:bg-blue-800'
                              : 'bg-gray-100 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200 border-gray-300 dark:border-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-700 hover:border-gray-400 dark:hover:border-zinc-600 active:bg-gray-300 dark:active:bg-zinc-600'}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Keyboard Shortcuts */}
                  <div className="pt-2 border-t border-gray-200 dark:border-zinc-700">
                    <div className="text-[11px] uppercase mb-1.5 text-gray-500 dark:text-zinc-500 font-medium">
                      Keyboard Shortcuts
                    </div>
                    <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px]">
                      {KEYBOARD_SHORTCUTS.map(({ keys, action }) => (
                        <div key={keys} className="flex justify-between">
                          <span className="text-gray-600 dark:text-zinc-400 font-mono">{keys}</span>
                          <span className="text-gray-500 dark:text-zinc-500">{action}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Session ID */}
                  <div className="pt-2 mt-2 border-t border-gray-200 dark:border-zinc-700">
                    <div className="text-[10px] text-gray-400 dark:text-zinc-500 font-mono truncate">
                      Session: {activeSessionId}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* AST Controls - show when AST is running */}
          {isASTRunning && (
            <div className="flex items-center gap-2 ml-2 pl-2 border-l border-zinc-700">
              <span className={`text-xs mr-1 flex items-center gap-1 ${isPaused ? 'text-yellow-400' : 'text-yellow-400 animate-pulse'}`}>
                {isPaused ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />} {runningAST}
              </span>
              <Tooltip content={isPaused ? 'Resume AST execution' : 'Pause after current item completes or fails'} position="bottom">
                <button
                  onClick={() => {
                    if (isPaused) {
                      resumeAST();
                    } else {
                      pauseAST();
                    }
                  }}
                  className="px-3 py-1.5 text-xs rounded border cursor-pointer transition-colors
                    bg-yellow-600 text-white border-yellow-600 hover:bg-yellow-700"
                >
                  {isPaused ? 'Resume' : 'Pause'}
                </button>
              </Tooltip>
              <Tooltip content="Stop after current item completes or fails" position="bottom">
                <button
                  onClick={() => cancelAST()}
                  className="px-3 py-1.5 text-xs rounded border cursor-pointer transition-colors
                    bg-red-600 text-white border-red-600 hover:bg-red-700"
                >
                  Stop
                </button>
              </Tooltip>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-zinc-300 text-xs">
            Cursor: ({cursorPosition.row},{cursorPosition.col})
          </span>
          {status === 'disconnected' || status === 'error' ? (
            <button
              onClick={connect}
              className="px-3 py-1.5 text-xs bg-blue-600 text-white rounded cursor-pointer hover:bg-blue-700 transition-colors"
            >
              Connect
            </button>
          ) : status === 'connected' ? (
            <button
              onClick={disconnect}
              className="px-3 py-1.5 text-xs rounded cursor-pointer transition-colors
                bg-gray-200 dark:bg-zinc-700 text-gray-700 dark:text-zinc-200 
                hover:bg-gray-300 dark:hover:bg-zinc-600"
            >
              Disconnect
            </button>
          ) : null}
        </div>
      </div>

      {/* Terminal container */}
      <div
        ref={terminalRef}
        className="p-1"
        onClick={focus}
      />
    </div>
  );
}
