import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '@/lib/api';

interface SessionConfig {
  kbIds?: string[];
  docIds?: string[];
  allowWebSearch?: boolean;
  isKBLocked?: boolean;
  sourceType?: string;
}

interface ChatSession {
  id: string;
  config?: SessionConfig;
}

interface UseSessionRestoreOptions {
  chatSessions: ChatSession[];
  currentSessionId?: string;
  sourceType?: 'home' | 'knowledge' | 'favorites';
  localStorageKey: string;
  onRestore: (session: ChatSession, sessionId: string) => Promise<void>;
}

interface UseSessionRestoreReturn {
  isRestoring: boolean;
}

/**
 * Custom hook to handle session restoration logic
 * Manages URL parameters and localStorage with proper priority
 */
export function useSessionRestore(options: UseSessionRestoreOptions): UseSessionRestoreReturn {
  const {
    chatSessions,
    currentSessionId,
    sourceType = 'home',
    localStorageKey,
    onRestore
  } = options;

  const [searchParams, setSearchParams] = useSearchParams();
  const [isRestoring, setIsRestoring] = useState(false);
  const [hasRestoredFromLocalStorage, setHasRestoredFromLocalStorage] = useState(false);
  
  // Track if we've processed the URL parameter to avoid loops
  const processedUrlParamRef = useRef<string | null>(null);

  // Priority 1: Handle URL parameter (always process, not limited by hasRestoredFromLocalStorage)
  useEffect(() => {
    if (chatSessions.length === 0) return;

    const chatIdFromUrl = searchParams.get('chatId');

    if (chatIdFromUrl && chatIdFromUrl !== processedUrlParamRef.current) {
      processedUrlParamRef.current = chatIdFromUrl;

      if (chatIdFromUrl !== currentSessionId) {
        const session = chatSessions.find(s => s.id === chatIdFromUrl);

        if (session) {
          setIsRestoring(true);
          onRestore(session, chatIdFromUrl)
            .finally(() => setIsRestoring(false));
        } else {
          console.warn(`Session ${chatIdFromUrl} from URL not found`);
        }
      }

      // Clear URL parameter to keep URL clean
      setSearchParams({});
    }
  }, [chatSessions, currentSessionId, searchParams, setSearchParams, onRestore]);

  // Priority 2: Restore from localStorage (only on first load)
  useEffect(() => {
    if (chatSessions.length === 0) return;
    if (hasRestoredFromLocalStorage) return;
    if (searchParams.get('chatId')) return; // Skip if URL param is present

    try {
      const savedSessionId = localStorage.getItem(localStorageKey);
      
      if (savedSessionId) {
        const session = chatSessions.find(s => s.id === savedSessionId);
        
        if (session) {
          // Verify session belongs to the correct source type
          const sessionSourceType = session.config?.sourceType;
          if (!sessionSourceType || sessionSourceType === sourceType) {
            setIsRestoring(true);
            onRestore(session, savedSessionId)
              .finally(() => setIsRestoring(false));
          } else {
            // Clear invalid session from localStorage
            localStorage.removeItem(localStorageKey);
          }
        } else {
          // Clear non-existent session from localStorage
          localStorage.removeItem(localStorageKey);
        }
      }
    } catch (error) {
      console.error('Failed to restore session from localStorage:', error);
    }

    setHasRestoredFromLocalStorage(true);
  }, [chatSessions, hasRestoredFromLocalStorage, searchParams, localStorageKey, sourceType, onRestore]);

  return {
    isRestoring
  };
}
