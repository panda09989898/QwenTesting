/** Custom hooks for the application. */
import { useEffect, useCallback, useRef } from 'react';
import { useEditorStore, useAuthStore } from '../store';
import wsService from '../services/websocket';

/** Hook for managing WebSocket connection and real-time updates. */
export function useWebSocket(documentId: number | null) {
  const { token } = useAuthStore();
  const { 
    setContent, 
    setVersion, 
    setActiveUsers, 
    addActiveUser, 
    removeActiveUser,
    updateUserTyping,
    setIsTyping 
  } = useEditorStore();
  
  const isConnected = useRef(false);
  const typingTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    if (!documentId || !token) return;

    const connect = async () => {
      try {
        await wsService.connect(documentId, token);
        isConnected.current = true;
      } catch (error) {
        console.error('Failed to connect WebSocket:', error);
      }
    };

    connect();

    return () => {
      wsService.disconnect();
      isConnected.current = false;
    };
  }, [documentId, token]);

  // Handle incoming operations
  useEffect(() => {
    if (!documentId) return;

    const unsubscribeOperation = wsService.on('operation', (data) => {
      const typedData = data as { 
        operation?: { type: string; position: number; text?: string; length?: number };
        new_content?: string;
        version?: number;
      };
      
      if (typedData.new_content !== undefined) {
        setContent(typedData.new_content);
      }
      if (typedData.version !== undefined) {
        setVersion(typedData.version);
      }
    });

    const unsubscribePresence = wsService.on('presence', (data) => {
      const typedData = data as { 
        user_id: number; 
        username: string; 
        is_typing: boolean;
        left?: boolean;
      };
      
      if (typedData.left) {
        removeActiveUser(typedData.user_id);
      } else {
        updateUserTyping(typedData.user_id, typedData.is_typing);
      }
    });

    const unsubscribeSync = wsService.on('sync', (data) => {
      const typedData = data as { 
        content: string; 
        version: number; 
        active_users: Array<{ user_id: number; username: string; is_typing: boolean }> 
      };
      
      setContent(typedData.content);
      setVersion(typedData.version);
      setActiveUsers(typedData.active_users);
    });

    return () => {
      unsubscribeOperation();
      unsubscribePresence();
      unsubscribeSync();
    };
  }, [documentId, setContent, setVersion, setActiveUsers, addActiveUser, removeActiveUser, updateUserTyping]);

  // Send typing indicator with debounce
  const sendTypingIndicator = useCallback((isTyping: boolean) => {
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    setIsTyping(isTyping);
    wsService.sendPresence(isTyping);

    if (isTyping) {
      typingTimeoutRef.current = window.setTimeout(() => {
        wsService.sendPresence(false);
        setIsTyping(false);
      }, 2000);
    }
  }, [setIsTyping]);

  return {
    isConnected: isConnected.current && wsService.isConnected(),
    sendTypingIndicator,
  };
}

/** Hook for debouncing values. */
export function useDebounce<T>(value: T, delay: number): T {
  const debouncedValue = useRef<T>(value);

  useEffect(() => {
    const handler = setTimeout(() => {
      debouncedValue.current = value;
    }, delay);

    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue.current;
}

/** Hook for detecting dark mode preference. */
export function useDarkMode() {
  useEffect(() => {
    const root = document.documentElement;
    const isDark = root.classList.contains('dark');
    
    if (isDark) {
      root.style.setProperty('--color-bg', '#0f172a');
      root.style.setProperty('--color-surface', '#1e293b');
      root.style.setProperty('--color-text', '#f1f5f9');
    } else {
      root.style.setProperty('--color-bg', '#ffffff');
      root.style.setProperty('--color-surface', '#f8fafc');
      root.style.setProperty('--color-text', '#0f172a');
    }
  }, []);

  const toggleDarkMode = useCallback(() => {
    document.documentElement.classList.toggle('dark');
  }, []);

  return { toggleDarkMode };
}
