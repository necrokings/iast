// ============================================================================
// useTerminal Hook - xterm.js Integration
// ============================================================================

import { useRef, useEffect, useCallback, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { config } from '../config';
import type { ConnectionStatus, TerminalDimensions } from '../types';
import {
  createTerminalWebSocket,
  type TerminalWebSocket,
} from '../services/websocket';
import {
  type MessageEnvelope,
  type TerminalType,
  type TN3270Field,
  isDataMessage,
  isErrorMessage,
  isSessionCreatedMessage,
  isSessionDestroyedMessage,
  isPongMessage,
  isTN3270ScreenMessage,
} from '@terminal/shared';
import { generateSessionId } from '@terminal/shared';
import {
  getStoredSessionId,
  setStoredSessionId,
} from '../utils/storage';

export interface UseTerminalOptions {
  sessionId?: string;
  terminalType?: TerminalType;
  autoConnect?: boolean;
}

export interface UseTerminalReturn {
  terminalRef: React.RefObject<HTMLDivElement | null>;
  status: ConnectionStatus;
  dimensions: TerminalDimensions;
  sessionId: string;
  /** TN3270 field map (empty for PTY terminals) */
  fields: TN3270Field[];
  /** TN3270 cursor position */
  cursorPosition: { row: number; col: number };
  connect: () => void;
  disconnect: () => void;
  write: (data: string) => void;
  sendKey: (key: string) => void;
  resize: (cols: number, rows: number) => void;
  clear: () => void;
  focus: () => void;
  /** Move cursor to position (TN3270 only) */
  moveCursor: (row: number, col: number) => void;
  /** Check if a position is in an input field (TN3270) */
  isInputPosition: (row: number, col: number) => boolean;
}

export function useTerminal(options: UseTerminalOptions = {}): UseTerminalReturn {
  const { autoConnect = true, terminalType = 'pty' } = options;

  const terminalRef = useRef<HTMLDivElement | null>(null);
  const terminalInstance = useRef<Terminal | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);
  const wsRef = useRef<TerminalWebSocket | null>(null);

  // TN3270 uses fixed 80x43 (IBM-3278-4-E), PTY uses dynamic sizing
  const isTn3270 = terminalType === 'tn3270';
  const fixedCols = isTn3270 ? 80 : config.terminal.defaultCols;
  const fixedRows = isTn3270 ? 43 : config.terminal.defaultRows;

  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [dimensions, setDimensions] = useState<TerminalDimensions>({
    cols: fixedCols,
    rows: fixedRows,
  });
  
  // TN3270 field map and cursor tracking
  const [fields, setFields] = useState<TN3270Field[]>([]);
  const [cursorPosition, setCursorPosition] = useState<{ row: number; col: number }>({ row: 0, col: 0 });
  const fieldsRef = useRef<TN3270Field[]>([]);

  // Get or create session ID
  const [sessionId] = useState<string>(() => {
    if (options.sessionId) return options.sessionId;
    const stored = getStoredSessionId();
    if (stored) return stored;
    const newId = generateSessionId();
    setStoredSessionId(newId);
    return newId;
  });

  // Handle incoming messages
  const handleMessage = useCallback((message: MessageEnvelope): void => {
    if (!terminalInstance.current) return;

    if (isDataMessage(message)) {
      terminalInstance.current.write(message.payload);
    } else if (isTN3270ScreenMessage(message)) {
      // TN3270 screen update with field information
      terminalInstance.current.write(message.payload);
      // Update field map
      setFields(message.meta.fields);
      fieldsRef.current = message.meta.fields;
      setCursorPosition({ row: message.meta.cursorRow, col: message.meta.cursorCol });
    } else if (isErrorMessage(message)) {
      terminalInstance.current.write(`\r\n\x1b[31mError: ${message.payload}\x1b[0m\r\n`);
    } else if (isSessionCreatedMessage(message)) {
      terminalInstance.current.write(`\r\n\x1b[32mSession started (shell: ${message.meta.shell})\x1b[0m\r\n`);
    } else if (isSessionDestroyedMessage(message)) {
      terminalInstance.current.write(`\r\n\x1b[33mSession ended\x1b[0m\r\n`);
    } else if (isPongMessage(message)) {
      // Heartbeat response, ignore
    }
  }, []);

  // Handle status changes
  const handleStatusChange = useCallback((newStatus: ConnectionStatus): void => {
    setStatus(newStatus);
  }, []);

  // Handle errors - only show persistent errors, not transient connection issues
  const handleError = useCallback((error: Error): void => {
    console.error('Terminal WebSocket error:', error);
    // Only show error in terminal if it's a permanent failure (max reconnects reached)
    // Transient "WebSocket error" messages during reconnection are not shown
    if (terminalInstance.current && error.message !== 'WebSocket error') {
      terminalInstance.current.write(`\r\n\x1b[31mConnection error: ${error.message}\x1b[0m\r\n`);
    }
  }, []);

  // Check if a position is in an unprotected (input) field
  const isInputPosition = useCallback((row: number, col: number): boolean => {
    if (!isTn3270) return true; // PTY terminals allow input anywhere
    
    const currentFields = fieldsRef.current;
    if (currentFields.length === 0) return false; // No fields defined = no input
    
    const cols = fixedCols;
    const addr = row * cols + col;
    
    for (const field of currentFields) {
      // Check if address is within this field
      if (field.end > field.start) {
        // Normal case - no wrap
        if (addr >= field.start && addr < field.end) {
          return !field.protected;
        }
      } else {
        // Wrap-around case
        if (addr >= field.start || addr < field.end) {
          return !field.protected;
        }
      }
    }
    
    // Position not in any field = protected
    return false;
  }, [isTn3270, fixedCols]);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || terminalInstance.current) return;

    const terminal = new Terminal({
      cursorBlink: config.terminal.cursorBlink,
      fontSize: config.terminal.fontSize,
      fontFamily: config.terminal.fontFamily,
      scrollback: isTn3270 ? 0 : config.terminal.scrollback, // No scrollback for 3270
      cols: fixedCols,
      rows: fixedRows,
      theme: {
        background: '#0a0a0c',
        foreground: '#e4e4e7',
        cursor: '#a1a1aa',
        selectionBackground: '#3f3f46',
        black: '#09090b',
        red: '#ef4444',
        green: '#22c55e',
        yellow: '#eab308',
        blue: '#3b82f6',
        magenta: '#a855f7',
        cyan: '#06b6d4',
        white: '#f4f4f5',
        brightBlack: '#52525b',
        brightRed: '#f87171',
        brightGreen: '#4ade80',
        brightYellow: '#facc15',
        brightBlue: '#60a5fa',
        brightMagenta: '#c084fc',
        brightCyan: '#22d3ee',
        brightWhite: '#fafafa',
      },
    });

    const fit = new FitAddon();
    const webLinks = new WebLinksAddon();

    terminal.loadAddon(fit);
    terminal.loadAddon(webLinks);

    terminal.open(terminalRef.current);
    
    // Only fit to container for PTY, TN3270 uses fixed size
    if (!isTn3270) {
      fit.fit();
    }

    terminalInstance.current = terminal;
    fitAddon.current = fit;

    // Handle user input
    terminal.onData((data: string): void => {
      // Send all input to backend - the tnz library handles field protection
      wsRef.current?.sendData(data);
    });

    // Handle resize - only for PTY terminals
    const handleResize = (): void => {
      if (!isTn3270 && fitAddon.current) {
        fitAddon.current.fit();
        if (terminalInstance.current) {
          const newDims = {
            cols: terminalInstance.current.cols,
            rows: terminalInstance.current.rows,
          };
          setDimensions(newDims);
          wsRef.current?.sendResize(newDims.cols, newDims.rows);
        }
      }
    };

    window.addEventListener('resize', handleResize);

    // For TN3270, track cursor position on any cursor movement
    let cursorDisposable: { dispose: () => void } | null = null;
    if (isTn3270) {
      // Poll cursor position periodically to catch arrow key movements
      const cursorInterval = setInterval(() => {
        if (terminalInstance.current) {
          const row = terminalInstance.current.buffer.active.cursorY;
          const col = terminalInstance.current.buffer.active.cursorX;
          setCursorPosition(prev => {
            if (prev.row !== row || prev.col !== col) {
              return { row, col };
            }
            return prev;
          });
        }
      }, 50);
      
      cursorDisposable = { dispose: () => clearInterval(cursorInterval) };
    }

    // For TN3270, add click handler to move cursor using mousedown on the xterm viewport
    let clickHandler: ((e: Event) => void) | null = null;
    if (isTn3270) {
      // Wait a tick for xterm to render, then attach to the viewport
      setTimeout(() => {
        const viewport = terminalRef.current?.querySelector('.xterm-screen');
        if (viewport) {
          clickHandler = (e: Event): void => {
            if (!terminalInstance.current) return;
            const mouseEvent = e as MouseEvent;
            
            const rect = viewport.getBoundingClientRect();
            const cellWidth = rect.width / fixedCols;
            const cellHeight = rect.height / fixedRows;
            
            // Calculate which cell was clicked
            const col = Math.floor((mouseEvent.clientX - rect.left) / cellWidth);
            const row = Math.floor((mouseEvent.clientY - rect.top) / cellHeight);
            
            // Clamp to valid range
            const clampedCol = Math.max(0, Math.min(col, fixedCols - 1));
            const clampedRow = Math.max(0, Math.min(row, fixedRows - 1));
            
            // Move cursor using ANSI escape sequence (1-indexed)
            terminalInstance.current.write(`\x1b[${clampedRow + 1};${clampedCol + 1}H`);
            setCursorPosition({ row: clampedRow, col: clampedCol });
          };
          
          viewport.addEventListener('mousedown', clickHandler);
        }
      }, 100);
    }

    // Create WebSocket connection
    wsRef.current = createTerminalWebSocket(sessionId, {
      onMessage: handleMessage,
      onStatusChange: handleStatusChange,
      onError: handleError,
    }, terminalType);

    if (autoConnect) {
      wsRef.current.connect();
    }

    return (): void => {
      window.removeEventListener('resize', handleResize);
      cursorDisposable?.dispose();
      if (clickHandler) {
        const viewport = terminalRef.current?.querySelector('.xterm-screen');
        viewport?.removeEventListener('mousedown', clickHandler);
      }
      wsRef.current?.disconnect();
      terminal.dispose();
      terminalInstance.current = null;
      fitAddon.current = null;
    };
  }, [sessionId, autoConnect, terminalType, handleMessage, handleStatusChange, handleError, isTn3270, fixedCols, fixedRows, isInputPosition]);

  const connect = useCallback((): void => {
    wsRef.current?.connect();
  }, []);

  const disconnect = useCallback((): void => {
    wsRef.current?.disconnect();
  }, []);

  const write = useCallback((data: string): void => {
    terminalInstance.current?.write(data);
  }, []);

  const sendKey = useCallback((key: string): void => {
    wsRef.current?.sendData(key);
  }, []);

  const resize = useCallback((cols: number, rows: number): void => {
    if (terminalInstance.current) {
      terminalInstance.current.resize(cols, rows);
      setDimensions({ cols, rows });
      wsRef.current?.sendResize(cols, rows);
    }
  }, []);

  const clear = useCallback((): void => {
    terminalInstance.current?.clear();
  }, []);

  const focus = useCallback((): void => {
    terminalInstance.current?.focus();
  }, []);

  // Move cursor to a specific position (TN3270)
  const moveCursor = useCallback((row: number, col: number): void => {
    if (!terminalInstance.current) return;
    // Move xterm cursor using ANSI escape sequence (1-indexed)
    terminalInstance.current.write(`\x1b[${row + 1};${col + 1}H`);
    setCursorPosition({ row, col });
  }, []);

  return {
    terminalRef,
    status,
    dimensions,
    sessionId,
    fields,
    cursorPosition,
    connect,
    disconnect,
    write,
    sendKey,
    resize,
    clear,
    focus,
    moveCursor,
    isInputPosition,
  };
}
