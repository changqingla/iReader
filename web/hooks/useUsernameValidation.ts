import { useState, useCallback, useRef } from 'react';
import { authAPI } from '@/lib/api';

interface UseUsernameValidationResult {
  isAvailable: boolean | null;
  isValidating: boolean;
  error: string | null;
  validateUsername: (username: string) => void;
  resetValidation: () => void;
}

// 简单的 debounce 实现，如果不想引入 lodash
function simpleDebounce<T extends (...args: any[]) => void>(func: T, wait: number) {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

export function useUsernameValidation(currentUsername?: string): UseUsernameValidationResult {
  const [isAvailable, setIsAvailable] = useState<boolean | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkUsername = useCallback(async (username: string) => {
    if (!username || username.trim() === '') {
      setIsAvailable(null);
      setIsValidating(false);
      return;
    }

    // 如果用户名没有变化，不需要校验
    if (currentUsername && username === currentUsername) {
      setIsAvailable(true);
      setIsValidating(false);
      return;
    }

    try {
      const response = await authAPI.checkUsername(username);
      setIsAvailable(response.available);
      setError(response.available ? null : '用户名已被占用');
    } catch (err: any) {
      setError(err.message || '校验失败');
      setIsAvailable(null);
    } finally {
      setIsValidating(false);
    }
  }, [currentUsername]);

  const debouncedCheck = useRef(simpleDebounce(checkUsername, 500)).current;

  const validateUsername = useCallback((username: string) => {
    setIsAvailable(null);
    setError(null);
    
    if (username.length < 3) {
      setError('用户名至少3个字符');
      return;
    }

    if (username.length > 20) {
      setError('用户名最多20个字符');
      return;
    }
    
    // 只允许字母、数字、下划线、中文
    if (!/^[\w\u4e00-\u9fa5]+$/.test(username)) {
      setError('只允许字母、数字、下划线和中文');
      return;
    }

    if (currentUsername && username === currentUsername) {
      setIsAvailable(true);
      return;
    }

    setIsValidating(true);
    debouncedCheck(username);
  }, [currentUsername, debouncedCheck]);

  const resetValidation = useCallback(() => {
    setIsAvailable(null);
    setIsValidating(false);
    setError(null);
  }, []);

  return {
    isAvailable,
    isValidating,
    error,
    validateUsername,
    resetValidation,
  };
}

