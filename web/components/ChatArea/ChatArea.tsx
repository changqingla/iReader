import React, { useState } from 'react';
import { Paperclip, Send } from 'lucide-react';
import styles from './ChatArea.module.css';

interface ChatAreaProps {
  selectedChatId?: string;
}

export default function ChatArea({ selectedChatId }: ChatAreaProps) {
  const [mode, setMode] = useState<'deep' | 'search'>('deep');
  const placeholder = mode === 'deep' ? '总结一下《Attention is all you need》这篇论文' : '搜索你感兴趣的知识库或主题';
  return (
    <div className={styles.chatArea}>
      {!selectedChatId && (
        <div className={styles.hero}>
          <div className={styles.heroInner}>
            <h1 className={styles.heading}>用 <span className={styles.em}>提问</span> 发现世界</h1>
          

            <div className={styles.askCard}>
              <div className={styles.askRow}>
                <button className={styles.heroAttachButton} aria-label="上传文件">
                  <Paperclip size={20} />
                </button>
                <input className={styles.askInput} placeholder={placeholder} />
              </div>
              <div className={styles.chipsRow}>
                <div className={styles.chipsGroup}>
                  <button
                    className={`${styles.pill} ${mode === 'deep' ? styles.pillActive : ''}`}
                    onClick={() => setMode('deep')}
                    aria-pressed={mode === 'deep'}
                  >深度思考</button>
                  <button
                    className={`${styles.pill} ${mode === 'search' ? styles.pillActive : ''}`}
                    onClick={() => setMode('search')}
                    aria-pressed={mode === 'search'}
                  >联网搜索</button>
                </div>
                <button className={styles.heroSendButton} aria-label="发送">
                  <Send size={18} />
                </button>
              </div>
            </div>

            <div className={styles.sections}>
              <div className={styles.col}>
                <div className={styles.colTitle}>推荐知识库</div>
                <div className={styles.kbItem}>
                  <div className={styles.kbAvatar}>📚</div>
                  <div className={styles.kbBody}>
                    <div className={styles.kbTitle}>（冰冻）的故事与人物</div>
                    <div className={styles.kbMeta}>48 人订阅 · 7 个内容</div>
                  </div>
                </div>
                <div className={styles.kbItem}>
                  <div className={styles.kbAvatar}>🤖</div>
                  <div className={styles.kbBody}>
                    <div className={styles.kbTitle}>AI 智能体</div>
                    <div className={styles.kbMeta}>182 人订阅 · 2 个内容</div>
                  </div>
                </div>
              </div>
              <div className={styles.col}>
                <div className={styles.colTitle}>想了解点什么？</div>
                <div className={styles.suggests}>
                  {['如何使用 DeepSeek 联网？','“低密经络”为主题架构是伪框架','人形机器人如何与人类和谐共处？'].map(t => (
                    <button key={t} className={styles.suggestChip}>{t}</button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}