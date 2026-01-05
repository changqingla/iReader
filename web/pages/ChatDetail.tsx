import React, { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Sidebar from '@/components/Sidebar/Sidebar';
import OptimizedMarkdown from '@/components/OptimizedMarkdown';
import { ArrowLeft, Menu, Copy, RefreshCw, ThumbsUp, ThumbsDown, Sparkles, ChevronDown, ChevronUp, FileText, Target } from 'lucide-react';
import { useRAGChat } from '@/hooks/useRAGChat';
import { useToast } from '@/hooks/useToast';
import { saveConversationToNoteById } from '@/utils/noteUtils';
import DocumentProgress from '@/components/DocumentProgress/DocumentProgress';
import DualColumnLayout, { shouldUseDualLayout } from '@/components/DualColumnLayout/DualColumnLayout';
import SendStopButton from '@/components/SendStopButton';
import styles from './ChatDetail.module.css';

// 任务类型选项配置
const MODE_TYPE_OPTIONS = [
  { value: undefined, label: '🤖 自动识别', icon: Sparkles },
  { value: 'SIMPLE_INTERACTION', label: '💬 简单互动', icon: Target },
  { value: 'LITERATURE_SUMMARY', label: '📄 文献总结', icon: FileText },
  { value: 'REVIEW_GENERATION', label: '📚 综述生成', icon: FileText },
  { value: 'DOCUMENT_COMPARISON', label: '🔍 文章对比', icon: Target },
  { value: 'LITERATURE_QA', label: '❓ 文献问答', icon: Target },
];

export default function ChatDetail() {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [inputMessage, setInputMessage] = useState('');
  const [chatMode, setChatMode] = useState<'deep' | 'search'>('deep');
  const [selectedModeType, setSelectedModeType] = useState<string | undefined>(undefined);
  
  // 消息反馈状态
  const [likedMessages, setLikedMessages] = useState<Set<string>>(new Set());
  const [dislikedMessages, setDislikedMessages] = useState<Set<string>>(new Set());
  const [collapsedThinking, setCollapsedThinking] = useState<Set<string>>(new Set());
  const [savedToNotes, setSavedToNotes] = useState<Set<string>>(new Set()); // 已保存到笔记的消息ID
  const [showRegenerateMenu, setShowRegenerateMenu] = useState<string | null>(null); // 显示重新生成菜单的消息ID
  const collapseTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);

  // 处理滚动事件
  const handleScroll = React.useCallback(() => {
    if (chatContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
      // 如果距离底部小于 100px，则认为在底部
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
      shouldAutoScrollRef.current = isAtBottom;
    }
  }, []);
  
  // RAG Chat Hook
  const { messages, isStreaming, sendMessage, regenerateLastMessage, stopGeneration, documentProgress, totalDocCount } = useRAGChat({
    mode: chatMode,
    onError: (error) => toast.error(`对话错误: ${error}`),
    onFirstContentToken: (messageId) => {
      // 当第一个 content token 到达时，自动折叠 thinking
      setCollapsedThinking(prev => {
        const newSet = new Set(prev);
        newSet.add(messageId);
        return newSet;
      });
    },
    onStopComplete: () => toast.info('已停止生成')  // 停止生成完成时显示提示
  });

  // 自动滚动到最新消息并处理历史记录中的思考折叠
  React.useEffect(() => {
    // 历史记录加载完成后，自动折叠所有思考部分并滚动到底部
    if (messages.length > 0) {
      // 自动折叠所有已完成的AI消息的思考部分
      const completedAIMessages = messages.filter(msg => 
        msg.role === 'assistant' && msg.thinking && msg.content
      );
      
      if (completedAIMessages.length > 0) {
        setCollapsedThinking(prev => {
          const newSet = new Set(prev);
          completedAIMessages.forEach(msg => newSet.add(msg.id));
          return newSet;
        });
      }
      
      // 滚动到底部 - 使用锚点元素而非scrollHeight
      setTimeout(() => {
        if (messagesEndRef.current) {
          messagesEndRef.current.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        }
      }, 100);
    }
  }, [messages.length]); // 只在消息数量变化时触发

  // 流式传输时的自动滚动
  React.useEffect(() => {
    if (isStreaming && shouldAutoScrollRef.current && messagesEndRef.current) {
      // 使用锚点元素滚动，避免scrollHeight计算不准确
      messagesEndRef.current.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
  }, [messages, isStreaming]);

  // 点击外部关闭重新生成菜单
  useEffect(() => {
    const handleClickOutside = () => {
      setShowRegenerateMenu(null);
    };

    if (showRegenerateMenu) {
      const timer = setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside);
      }, 0);
      return () => {
        clearTimeout(timer);
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showRegenerateMenu]);

  const handleSendMessage = () => {
    if (!inputMessage.trim() || isStreaming) return;
    shouldAutoScrollRef.current = true; // 发送新消息时强制滚动
    sendMessage(inputMessage, selectedModeType);
    setInputMessage('');
  };

  const handleCopyMessage = async (content: string) => {
    try {
      // 优先使用现代 Clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(content);
      } else {
        // 降级方案：使用传统方法
        const textArea = document.createElement('textarea');
        textArea.value = content;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        try {
          document.execCommand('copy');
          textArea.remove();
        } catch (err) {
          console.error('降级复制方法失败:', err);
          textArea.remove();
          throw err;
        }
      }
      // toast.success('已复制到剪贴板');
    } catch (err) {
      console.error('复制失败:', err);
      toast.error('复制失败，请重试');
    }
  };

  const handleLikeMessage = (messageId: string) => {
    setLikedMessages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
        setDislikedMessages(prev => {
          const newDisliked = new Set(prev);
          newDisliked.delete(messageId);
          return newDisliked;
        });
      }
      return newSet;
    });
  };

  const handleDislikeMessage = (messageId: string) => {
    setDislikedMessages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
        setLikedMessages(prev => {
          const newLiked = new Set(prev);
          newLiked.delete(messageId);
          return newLiked;
        });
      }
      return newSet;
    });
  };

  // 保存对话到笔记
  const handleSaveToNotes = async (messageId: string) => {
    if (savedToNotes.has(messageId)) {
      toast.info('该对话已保存到笔记');
      return;
    }

    try {
      const result = await saveConversationToNoteById(messages, messageId);

      if (result.success) {
        setSavedToNotes(prev => new Set(prev).add(messageId));
        toast.success('已保存到笔记');
      } else {
        toast.error(result.error || '保存失败');
      }
    } catch (error: any) {
      console.error('保存到笔记失败:', error);
      toast.error('保存失败，请重试');
    }
  };

  const toggleThinkingCollapse = (messageId: string) => {
    // 清除之前的定时器
    if (collapseTimeoutRef.current) {
      clearTimeout(collapseTimeoutRef.current);
    }
    
    setCollapsedThinking(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  return (
    <div className={styles.chatDetail}>
      {/* Mobile Sidebar Overlay */}
      {isMobile && isSidebarOpen && (
        <div className={styles.overlay} onClick={() => setIsSidebarOpen(false)} />
      )}
      
      {/* Sidebar */}
      <div className={`${styles.sidebarContainer} ${isMobile && isSidebarOpen ? styles.open : ''}`}>
        <Sidebar
          onNewChat={() => navigate('/')}
          onSelectChat={(id) => navigate(`/chat/${id}`)}
          selectedChatId={chatId}
        />
      </div>

      {/* Main Content */}
      <div className={styles.mainContent}>
        {/* Header */}
        <div className={styles.header}>
          {isMobile && (
            <button onClick={() => setIsSidebarOpen(true)} className={styles.menuButton}>
              <Menu size={24} />
            </button>
          )}
          <button onClick={() => navigate('/')} className={styles.backButton}>
            <ArrowLeft size={20} />
          </button>
          <h1 className={styles.title}>对话详情</h1>
        </div>

        {/* Messages Area */}
        <div 
          className={styles.messagesContainer}
          ref={chatContainerRef}
          onScroll={handleScroll}
        >
          {messages.map((msg, index) => (
            <div 
              key={msg.id}
              className={msg.role === 'user' ? styles.userMessage : styles.aiMessage}
            >
              {/* 双栏布局：多文档任务时使用 */}
              {msg.role === 'assistant' && index === messages.length - 1 && shouldUseDualLayout(documentProgress, msg, isStreaming, totalDocCount) ? (
                <DualColumnLayout
                  message={msg}
                  isStreaming={isStreaming}
                  documentProgress={documentProgress}
                  isLastMessage={index === messages.length - 1}
                />
              ) : (
                <>
                  {/* 单栏布局：普通消息 */}
                  {/* 思考过程（仅AI消息且有思考内容时显示） */}
                  {msg.role === 'assistant' && msg.thinking && (
                    <div className={styles.thinkingProcess}>
                      <div 
                        className={styles.thinkingHeader}
                        onClick={() => toggleThinkingCollapse(msg.id)}
                        style={{ cursor: 'pointer' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Sparkles size={14} />
                          <span>思考过程</span>
                        </div>
                        {collapsedThinking.has(msg.id) ? (
                          <ChevronDown size={16} />
                        ) : (
                          <ChevronUp size={16} />
                        )}
                      </div>
                      {!collapsedThinking.has(msg.id) && (
                        <div className={styles.thinkingContent}>
                          <OptimizedMarkdown>
                            {msg.thinking}
                          </OptimizedMarkdown>
                          {/* 文档处理进度（仅在多文档任务且是最后一条消息时显示） */}
                          {index === messages.length - 1 && documentProgress.size > 0 && (
                            <DocumentProgress 
                              documents={Array.from(documentProgress.values())}
                              isStreaming={isStreaming}
                            />
                          )}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* 如果思考完成但答案未到达，显示生成提示 */}
                  {msg.role === 'assistant' && msg.thinking && !msg.content && isStreaming && (
                    <div className={styles.generatingAnswer}>
                      <div className={styles.thinkingDots}>
                        <span className={styles.dot}></span>
                        <span className={styles.dot}></span>
                        <span className={styles.dot}></span>
                      </div>
                      <span className={styles.thinkingText}>正在生成答案...</span>
                    </div>
                  )}
                  
                  {/* 最终回答 */}
                  {msg.content && (
                    <div className={styles.messageContent}>
                      {msg.role === 'user' ? (
                        msg.content
                      ) : (
                        <OptimizedMarkdown>{msg.content}</OptimizedMarkdown>
                      )}
                    </div>
                  )}
                </>
              )}

              {/* 后续问题（仅AI消息且有后续问题时显示） */}
              {msg.role === 'assistant' && msg.followUpQuestions && msg.followUpQuestions.length > 0 && (
                <div className={styles.followUpQuestions}>
                  <div className={styles.followUpTitle}>
                    <Sparkles size={13} />
                    <span>猜你想问</span>
                  </div>
                  <div className={styles.questionList}>
                    {msg.followUpQuestions.map((question, qIndex) => (
                      <button
                        key={qIndex}
                        className={styles.questionButton}
                        onClick={() => {
                          if (!isStreaming) {
                            setInputMessage(question);
                          }
                        }}
                        disabled={isStreaming}
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* AI 消息操作按钮 - 只在流式输出完成后显示 */}
              {msg.role === 'assistant' && msg.content && (!isStreaming || index !== messages.length - 1) && (
                <div className={styles.messageActions}>
                  <button
                    className={styles.actionButton}
                    onClick={() => handleCopyMessage(msg.content)}
                    title="复制"
                  >
                    <Copy size={16} />
                  </button>
                  <button
                    className={`${styles.actionButton} ${likedMessages.has(msg.id) ? styles.liked : ''}`}
                    onClick={() => handleLikeMessage(msg.id)}
                    title={likedMessages.has(msg.id) ? "取消点赞" : "点赞"}
                  >
                    <ThumbsUp size={16} />
                  </button>
                  <button
                    className={`${styles.actionButton} ${dislikedMessages.has(msg.id) ? styles.disliked : ''}`}
                    onClick={() => handleDislikeMessage(msg.id)}
                    title={dislikedMessages.has(msg.id) ? "取消点踩" : "点踩"}
                  >
                    <ThumbsDown size={16} />
                  </button>
                  <button
                    className={`${styles.actionButton} ${savedToNotes.has(msg.id) ? styles.saved : ''}`}
                    onClick={() => handleSaveToNotes(msg.id)}
                    title={savedToNotes.has(msg.id) ? "已保存到笔记" : "保存到笔记"}
                  >
                    <FileText size={16} />
                  </button>
                  <div className={styles.regenerateWrapper}>
                    <button
                      className={styles.actionButton}
                      onClick={() => regenerateLastMessage()}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setShowRegenerateMenu(showRegenerateMenu === msg.id ? null : msg.id);
                      }}
                      title="重新生成（右键查看更多选项）"
                    >
                      <RefreshCw size={16} />
                    </button>
                    {showRegenerateMenu === msg.id && (
                      <div className={styles.regenerateMenu}>
                        <button
                          className={styles.regenerateMenuItem}
                          onClick={() => {
                            regenerateLastMessage();
                            setShowRegenerateMenu(null);
                          }}
                        >
                          🔄 重新生成
                        </button>
                        <button
                          className={styles.regenerateMenuItem}
                          onClick={() => {
                            regenerateLastMessage(true);
                            setShowRegenerateMenu(null);
                          }}
                          title="重新生成文档总结并刷新缓存"
                        >
                          🔃 重新生成（刷新缓存）
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
          {isStreaming && (
            <div className={styles.streamingIndicator}>
              <div className={styles.loadingDots}>
                <span>.</span><span>.</span><span>.</span>
              </div>
              <span>AI 正在思考...</span>
            </div>
          )}
          <div ref={messagesEndRef} style={{ height: 0, overflow: 'hidden' }} />
        </div>

        {/* Input Area */}
        <div className={styles.inputArea}>
          <div className={styles.modeSwitch}>
            <button
              className={chatMode === 'deep' ? styles.modeActive : ''}
              onClick={() => setChatMode('deep')}
              disabled={isStreaming}
            >
              深度思考
            </button>
            <button
              className={chatMode === 'search' ? styles.modeActive : ''}
              onClick={() => setChatMode('search')}
              disabled={isStreaming}
            >
              联网搜索
            </button>
          </div>

          {/* 任务类型选择器 */}
          <div className={styles.modeTypeSelector}>
            <div className={styles.modeTypeLabel}>
              <Target size={14} />
              <span>任务类型</span>
            </div>
            <div className={styles.modeTypeOptions}>
              {MODE_TYPE_OPTIONS.map((option) => (
                <button
                  key={option.value || 'auto'}
                  className={`${styles.modeTypeOption} ${selectedModeType === option.value ? styles.active : ''}`}
                  onClick={() => setSelectedModeType(option.value)}
                  disabled={isStreaming}
                >
                  <span className={styles.modeTypeText}>{option.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className={styles.inputRow}>
            <input
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
                  handleSendMessage();
                }
              }}
              placeholder="继续对话..."
              className={styles.input}
              disabled={isStreaming}
            />
            <SendStopButton
              isStreaming={isStreaming}
              disabled={false}
              onSend={handleSendMessage}
              onStop={stopGeneration}
              hasContent={!!inputMessage.trim()}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

