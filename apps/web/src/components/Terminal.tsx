// ============================================================================
// Terminal Component
// ============================================================================

import { useEffect, useState, useRef } from 'react';
import { useTerminal } from '../hooks/useTerminal';
import type { ConnectionStatus } from '../types';
import type { TerminalType } from '@terminal/shared';
import '@xterm/xterm/css/xterm.css';

interface TerminalProps {
  sessionId?: string;
  terminalType?: TerminalType;
  autoConnect?: boolean;
  onStatusChange?: (status: ConnectionStatus) => void;
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

export function Terminal({ sessionId, terminalType = 'pty', autoConnect = true, onStatusChange }: TerminalProps): React.ReactNode {
  const {
    terminalRef,
    status,
    sessionId: activeSessionId,
    cursorPosition,
    connect,
    disconnect,
    focus,
    sendKey,
  } = useTerminal({ sessionId, terminalType, autoConnect });

  const isTn3270 = terminalType === 'tn3270';
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
    <div className={`flex flex-col h-full bg-zinc-950 ${isTn3270 ? 'w-fit' : 'w-full'}`}>
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
          
          {/* PF/PA Keys Dropdown for TN3270 */}
          {isTn3270 && status === 'connected' && (
            <div ref={menuRef} className="relative">
              <button
                onClick={() => setKeyMenuOpen(!keyMenuOpen)}
                className={`px-2 py-1 text-xs flex items-center gap-1 rounded border cursor-pointer transition-colors
                  ${keyMenuOpen 
                    ? 'bg-blue-600 text-white border-blue-600' 
                    : 'bg-gray-100 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200 border-gray-300 dark:border-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-700'}`}
              >
                Keys ▾
              </button>
              
              {keyMenuOpen && (
                <div className="absolute top-full left-0 mt-1 min-w-[280px] p-2 rounded-md border shadow-lg z-50 bg-white dark:bg-zinc-900 border-gray-200 dark:border-zinc-700">
                  {/* PF Keys */}
                  <div className="mb-2">
                    <div className="text-[10px] uppercase mb-1 text-gray-500 dark:text-zinc-500">
                      Function Keys
                    </div>
                    <div className="grid grid-cols-6 gap-0.5">
                      {PF_KEYS.map(({ label, key }) => (
                        <button
                          key={label}
                          onClick={() => handleKeyClick(key)}
                          className="px-1 py-1 text-[10px] rounded border cursor-pointer transition-colors
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
                  <div>
                    <div className="text-[10px] uppercase mb-1 text-gray-500 dark:text-zinc-500">
                      Program Attention & Actions
                    </div>
                    <div className="flex flex-wrap gap-0.5">
                      {PA_KEYS.map(({ label, key }) => (
                        <button
                          key={label}
                          onClick={() => handleKeyClick(key)}
                          className={`px-2 py-1 text-[10px] rounded border cursor-pointer transition-colors
                            ${label === 'Enter' 
                              ? 'bg-blue-600 text-white border-blue-600 hover:bg-blue-700 active:bg-blue-800' 
                              : 'bg-gray-100 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200 border-gray-300 dark:border-zinc-700 hover:bg-gray-200 dark:hover:bg-zinc-700 hover:border-gray-400 dark:hover:border-zinc-600 active:bg-gray-300 dark:active:bg-zinc-600'}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          {isTn3270 && (
            <span className="text-zinc-300 text-[11px]">
              Cursor: ({cursorPosition.row + 1},{cursorPosition.col + 1})
            </span>
          )}
          <span className="text-zinc-400 text-[11px]">
            Session: {activeSessionId}
          </span>
          {status === 'disconnected' || status === 'error' ? (
            <button
              onClick={connect}
              className="px-2 py-1 text-[11px] bg-blue-600 text-white rounded-sm cursor-pointer hover:bg-blue-700 transition-colors"
            >
              Connect
            </button>
          ) : status === 'connected' ? (
            <button
              onClick={disconnect}
              className="px-2 py-1 text-[11px] rounded-sm cursor-pointer transition-colors
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
        className={`p-1 ${isTn3270 ? '' : 'flex-1 overflow-hidden'}`}
        onClick={focus}
      />
    </div>
  );
}
