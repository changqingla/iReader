import React, { useEffect, useRef, useState } from 'react';
import { Send, Paperclip, Mic } from 'lucide-react';
import styles from './InputArea.module.css';

interface InputAreaProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
}

export default function InputArea({ onSendMessage, disabled = false }: InputAreaProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [maxInputHeight, setMaxInputHeight] = useState<number>(240);

  useEffect(() => {
    const updateMax = () => {
      const vh = window.innerHeight || 800;
      setMaxInputHeight(Math.max(160, Math.floor(vh * 0.4)));
    };
    updateMax();
    window.addEventListener('resize', updateMax);
    return () => window.removeEventListener('resize', updateMax);
  }, []);

  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    const next = Math.min(el.scrollHeight, maxInputHeight);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > maxInputHeight ? 'auto' : 'hidden';
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSendMessage(message.trim());
      setMessage('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.overflowY = 'hidden';
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className={styles.inputArea}>
      <form onSubmit={handleSubmit} className={styles.inputForm}>
        <div className={styles.inputContainer}>
          <button
            type="button"
            className={styles.attachButton}
            aria-label="Attach file"
          >
            <Paperclip size={18} />
          </button>
          
          <textarea
            ref={textareaRef}
            value={message}
            onChange={(e) => { setMessage(e.target.value); autoResize(); }}
            onKeyDown={(e) => { handleKeyDown(e); /* resize on Enter for new lines */ setTimeout(autoResize, 0); }}
            placeholder="Message ChatGPT..."
            className={styles.messageInput}
            rows={1}
            disabled={disabled}
          />
          
          <div className={styles.rightButtons}>
            <button
              type="button"
              className={styles.micButton}
              aria-label="Voice input"
            >
              <Mic size={18} />
            </button>
            
            <button
              type="submit"
              className={`${styles.sendButton} ${message.trim() ? styles.active : ''}`}
              disabled={!message.trim() || disabled}
              aria-label="Send message"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </form>
      
      <div className={styles.disclaimer}>
        ChatGPT can make mistakes. Check important info.
      </div>
    </div>
  );
}