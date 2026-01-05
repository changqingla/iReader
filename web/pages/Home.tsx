import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Sidebar from '@/components/Sidebar/Sidebar';
import OptimizedMarkdown from '@/components/OptimizedMarkdown';
import { useRAGChat } from '@/hooks/useRAGChat';
import { useToast } from '@/hooks/useToast';
import { useUserProfile } from '@/hooks/useUserProfile';
import { api, kbAPI } from '@/lib/api';
import { saveConversationToNoteById } from '@/utils/noteUtils';
import { getFileIcon } from '@/utils/fileIcons';
import { Menu, User, Sparkles, Search, Database, X, Check, Copy, ThumbsUp, ThumbsDown, ChevronDown, ChevronUp, FileText, MessageSquare, Target, BookOpen, Paperclip, RefreshCw } from 'lucide-react';
import aiAvatarUrl from '@/assets/ai.jpg';
import Tooltip from '@/components/Tooltip';
import DocumentProgress from '@/components/DocumentProgress/DocumentProgress';
import DualColumnLayout, { shouldUseDualLayout } from '@/components/DualColumnLayout/DualColumnLayout';
import { KnowledgeBaseSelector, SelectionState } from '@/components/KnowledgeBaseSelector';
import SendStopButton from '@/components/SendStopButton';
import styles from './Home.module.css';

// 附件类型定义
interface AttachedFile {
  file: File;
  id?: string; // 文档ID
  kbId?: string; // 知识库ID
  status: 'uploading' | 'parsing' | 'ready' | 'error';
  progress?: number;
}

// 支持的文件扩展名
const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.doc', '.docx'];
const MAX_FILES = 5;

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

// 任务类型选项配置
const TASK_TYPE_OPTIONS = [
  { 
    value: 'LITERATURE_SUMMARY', 
    label: '文献总结', 
    icon: FileText,
    desc: '快速提炼核心观点',
    color: 'cyan' 
  },
  { 
    value: 'REVIEW_GENERATION', 
    label: '综述生成', 
    icon: BookOpen,
    desc: '多篇文献深度综合',
    color: 'violet'
  },
  { 
    value: 'LITERATURE_QA', 
    label: '文献问答', 
    icon: MessageSquare,
    desc: '精准回答细节问题',
    color: 'amber'
  },
  { 
    value: 'DOCUMENT_COMPARISON', 
    label: '文章对比', 
    icon: Target,
    desc: '多篇文献异同分析',
    color: 'rose'
  },
];

export default function Home() {
  const toast = useToast();
  const navigate = useNavigate();
  const { profile } = useUserProfile();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [webSearch, setWebSearch] = useState(false);
  const [inputMessage, setInputMessage] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);

  // 处理滚动事件
  const handleScroll = useCallback(() => {
    if (chatContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 100;
      shouldAutoScrollRef.current = isAtBottom;
    }
  }, []);

  const [chatSessions, setChatSessions] = useState<any[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | undefined>(undefined);
  const [hasRestoredSession, setHasRestoredSession] = useState(false);
  
  // 轮询附件解析状态
  useEffect(() => {
    let pollTimer: NodeJS.Timeout;

    const checkStatus = async () => {
      // 检查所有处于 parsing 状态的文件
      const parsingFiles = attachedFiles.filter(f => f.status === 'parsing' && f.id && f.kbId);
      if (parsingFiles.length === 0) return;

      for (const file of parsingFiles) {
        try {
          const res = await kbAPI.getDocumentStatus(file.kbId!, file.id!);
          if (res.status === 'ready' || res.status === 'completed' || res.status === 'processed') {
            setAttachedFiles(prev => prev.map(f => 
              f.id === file.id ? { ...f, status: 'ready' } : f
            ));
          } else if (res.status === 'failed' || res.status === 'error') {
            setAttachedFiles(prev => prev.map(f => 
              f.id === file.id ? { ...f, status: 'error' } : f
            ));
            toast.error(`${file.file.name} 解析失败`);
          }
        } catch (error) {
          console.error('Failed to check document status:', error);
        }
      }
    };

    const hasParsingFiles = attachedFiles.some(f => f.status === 'parsing');
    if (hasParsingFiles) {
      pollTimer = setInterval(checkStatus, 2000);
      checkStatus(); // 立即检查一次
    }

    return () => {
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [attachedFiles]);

  // 处理文件上传点击
  const handleUploadClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  // 处理文件移除
  const handleRemoveFile = (index: number) => {
    const fileToRemove = attachedFiles[index];
    // 只有当文件有真实的 docId（不是临时 ID）时，才从 selectedDocIds 中移除
    if (fileToRemove?.id && !fileToRemove.id.startsWith('temp_')) {
      setSelectedDocIds(prev => prev.filter(id => id !== fileToRemove.id));
    }
    setAttachedFiles(prev => prev.filter((_, i) => i !== index));
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // 处理文件选择
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    // 检查文件数量限制
    const currentCount = attachedFiles.length;
    const newFilesCount = files.length;
    if (currentCount + newFilesCount > MAX_FILES) {
      toast.error(`最多只能上传 ${MAX_FILES} 个文件，当前已有 ${currentCount} 个`);
      e.target.value = '';
      return;
    }

    // 验证文件扩展名
    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        toast.error(`不支持的文件格式: ${file.name}`);
        continue;
      }
      validFiles.push(file);
    }

    if (validFiles.length === 0) {
      e.target.value = '';
      return;
    }

    // 查找"我的知识库"（默认知识库）
    let defaultKB = myKBs.find(kb => kb.name === '我的知识库');
    
    if (!defaultKB) {
      try {
        const myKBResponse = await api.listKnowledgeBases(undefined, 1, 50);
        const kbList = myKBResponse.items || [];
        defaultKB = kbList.find(kb => kb.name === '我的知识库');
        
        if (kbList.length > 0) {
          setMyKBs(kbList);
        }
      } catch (error) {
        console.error('Failed to load knowledge bases:', error);
      }
    }
    
    if (!defaultKB) {
      toast.error('未找到默认知识库');
      e.target.value = '';
      return;
    }

    // 清空 input 以便下次选择同一文件
    e.target.value = '';

    // 为每个文件创建初始状态并上传
    for (const file of validFiles) {
      // 使用唯一标识符来追踪文件
      const tempId = `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // 创建带有临时ID的文件记录
      const newFileRecord: AttachedFile = {
        file,
        id: tempId, // 临时使用 tempId，上传成功后会更新为真实 docId
        status: 'uploading'
      };
      
      setAttachedFiles(prev => [...prev, newFileRecord]);

      try {
        // 上传文件
        const response = await kbAPI.uploadDocument(defaultKB.id, file);
        const docId = response.id || response.doc_id || (response.document ? response.document.id : null);

        if (docId) {
          // 更新文件状态：通过 tempId 匹配
          setAttachedFiles(prev => prev.map(f => 
            f.id === tempId ? { ...f, id: docId, kbId: defaultKB.id, status: 'parsing' } : f
          ));
          
          // 将文档ID添加到选中列表
          setSelectedDocIds(prev => {
            if (!prev.includes(docId)) {
              return [...prev, docId];
            }
            return prev;
          });

          // 确保默认知识库被选中
          if (!selectedKBs.includes(defaultKB.id)) {
            setSelectedKBs(prev => [...prev, defaultKB.id]);
          }
        } else {
          throw new Error('未获取到文档ID');
        }
      } catch (error: any) {
        console.error('Failed to upload file:', error);
        toast.error(`${file.name} 上传失败`);
        // 更新为错误状态：通过 tempId 匹配
        setAttachedFiles(prev => prev.map(f => 
          f.id === tempId ? { ...f, status: 'error' } : f
        ));
      }
    }

    // 刷新知识库列表
    loadKnowledgeBases();
  };
  
  // 消息反馈状态
  const [likedMessages, setLikedMessages] = useState<Set<string>>(new Set());
  const [dislikedMessages, setDislikedMessages] = useState<Set<string>>(new Set());
  const [collapsedThinking, setCollapsedThinking] = useState<Set<string>>(new Set());
  const [isTogglingThinking, setIsTogglingThinking] = useState(false);
  const [savedToNotes, setSavedToNotes] = useState<Set<string>>(new Set()); // 已保存到笔记的消息ID
  const [copiedMessages, setCopiedMessages] = useState<Set<string>>(new Set()); // 已复制的消息ID
  const [selectedModeType, setSelectedModeType] = useState<string | undefined>(undefined); // 任务类型
  const [showRegenerateMenu, setShowRegenerateMenu] = useState<string | null>(null); // 显示重新生成菜单的消息ID
  
  // 知识库选择相关状态
  const [showKBSelector, setShowKBSelector] = useState(false);
  const [selectedKBs, setSelectedKBs] = useState<string[]>([]);
  const [myKBs, setMyKBs] = useState<any[]>([]);
  const [favoriteKBs, setFavoriteKBs] = useState<any[]>([]);
  const [loadingKBs, setLoadingKBs] = useState(false);
  const [isKBLocked, setIsKBLocked] = useState(false); // 知识库是否已锁定
  const kbButtonRef = useRef<HTMLButtonElement>(null); // 知识库按钮 ref
  const kbButtonRef2 = useRef<HTMLButtonElement>(null); // 对话界面的知识库按钮 ref
  const [kbPanelPosition, setKbPanelPosition] = useState<React.CSSProperties | null>(null);
  
  // 知识库文档缓存（用于会话恢复）
  const [kbDocuments, setKbDocuments] = useState<Record<string, any[]>>({});
  
  // 所有选中知识库的文档ID及其所属知识库映射
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [docToKbMap, setDocToKbMap] = useState<Record<string, string>>({});

  // 深度思考默认开启（始终显示思考过程）
  // mode 参数用于决定是否启用 deep_thinking
  const [deepThinking, setDeepThinking] = useState(true);
  
  // 根据选择确定mode：始终使用deep模式，通过deepThinking和webSearch参数控制具体行为
  const chatMode = 'deep';

  // 智能传递参数：
  // - 如果选择了知识库 → 传递所有文档ID（让后端判断单文档/多文档）
  // - 单文档 → 传递该文档所属的kb_id（后端会获取markdown content）
  // - 多文档 → 传递第一个知识库的ID（用于权限验证）
  // - 其他情况 → 后端使用召回模式
  const hasSelectedKB = selectedKBs.length > 0;
  
  // 确定传递哪个kb_id
  // ✅ 使用 useMemo 缓存 kbIdToPass 计算，避免每次渲染都重新计算
  const kbIdToPass = useMemo(() => {
    if (selectedKBs.length === 1) {
      // 单知识库：直接传该知识库ID
      return selectedKBs[0];
    } else if (selectedDocIds.length === 1 && docToKbMap[selectedDocIds[0]]) {
      // 多知识库但只有1个文档：传该文档所属的知识库ID（用于获取content）
      return docToKbMap[selectedDocIds[0]];
    } else if (selectedKBs.length > 1) {
      // 多知识库多文档：传第一个知识库ID（用于权限验证）
      return selectedKBs[0];
    }
    return undefined;
  }, [selectedKBs, selectedDocIds, docToKbMap]);

  // 加载聊天会话列表
  const loadChatSessions = useCallback(async () => {
    try {
      const response = await api.listChatSessions(1, 50);
      setChatSessions(response.sessions);
    } catch (error) {
      console.error('Failed to load chat sessions:', error);
    }
  }, []);

  // ✅ 使用 useCallback 包装回调函数，避免不必要的重新渲染
  const handleError = useCallback((error: string) => {
    toast.error(`对话错误: ${error}`);
  }, [toast]);

  const handleSessionCreated = useCallback((newSessionId: string) => {
    setCurrentSessionId(newSessionId);
    // 保存到 localStorage
    try {
      localStorage.setItem('home_last_session_id', newSessionId);
    } catch (error) {
      console.error('Failed to save session ID to localStorage:', error);
    }
    loadChatSessions();
  }, [loadChatSessions]);

  const handleFirstContentToken = useCallback((messageId: string) => {
    // 当第一个 content token 到达时，自动折叠 thinking
    setCollapsedThinking(prev => {
      const newSet = new Set(prev);
      newSet.add(messageId);
      return newSet;
    });
  }, []);

  const { messages, isStreaming, isLoading, sendMessage, clearMessages, regenerateLastMessage, stopGeneration, documentProgress, totalDocCount } = useRAGChat({
    sessionId: currentSessionId,
    kbId: kbIdToPass,                                   // 智能传递kb_id
    docIds: hasSelectedKB ? selectedDocIds : undefined, // 选择了知识库时传所有doc_ids
    mode: chatMode,
    enableWebSearch: webSearch,                         // 是否启用联网搜索
    showThinking: deepThinking,                         // 是否显示思考过程（深度思考模式）
    sourceType: 'home',                                 // 标记为首页会话
    onError: handleError,
    onSessionCreated: handleSessionCreated,
    onFirstContentToken: handleFirstContentToken,
    onStopComplete: () => toast.info('已停止生成')      // 停止生成完成时显示提示
  });

  // 加载知识库
  const loadKnowledgeBases = async () => {
    setLoadingKBs(true);
    try {
      const [myKBResponse, favoriteKBResponse] = await Promise.all([
        api.listKnowledgeBases(undefined, 1, 50),
        api.listFavoriteKBs(1, 50)
      ]);
      setMyKBs(myKBResponse.items || []);
      setFavoriteKBs(favoriteKBResponse.items || []);
    } catch (error) {
      console.error('Failed to load knowledge bases:', error);
      toast.error('加载知识库失败');
    } finally {
      setLoadingKBs(false);
    }
  };

  // 打开知识库选择器时加载知识库并计算位置
  const handleOpenKBSelector = (buttonRef?: React.RefObject<HTMLButtonElement>) => {
    const ref = buttonRef || kbButtonRef;
    
    if (ref?.current) {
      const rect = ref.current.getBoundingClientRect();
      const viewportHeight = window.innerHeight;
      const spaceAbove = rect.top;
      const spaceBelow = viewportHeight - rect.bottom;
      
      // 优先显示在上方，除非上方空间太小（小于300px）且下方空间更多
      // 使用 bottom 定位可以实现"从下往上长"的效果，避免高度不足时的悬空问题
      const showAbove = spaceAbove > 300 || spaceAbove > spaceBelow;
      
      let newPosition: React.CSSProperties = {
        left: Math.max(16, rect.left - 50), // 稍微向左偏移
      };

      if (showAbove) {
        // 显示在上方：定位到底部 = 视口高度 - 按钮顶部 + 间距
        newPosition.bottom = viewportHeight - rect.top + 8;
        newPosition.maxHeight = Math.min(400, spaceAbove - 16); // 留出一点顶部边距
      } else {
        // 显示在下方
        newPosition.top = rect.bottom + 8;
        newPosition.maxHeight = Math.min(400, spaceBelow - 16); // 留出一点底部边距
      }

      setKbPanelPosition(newPosition);
      setShowKBSelector(true);
      if (myKBs.length === 0 && favoriteKBs.length === 0) {
        loadKnowledgeBases();
      }
    }
  };

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 768);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 点击外部关闭重新生成菜单
  const regenerateMenuRef = useRef<HTMLDivElement>(null);
  
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // 检查点击是否在菜单内部
      if (regenerateMenuRef.current && regenerateMenuRef.current.contains(event.target as Node)) {
        // 点击在菜单内部，不关闭
        return;
      }
      // 点击在菜单外部，关闭菜单
      setShowRegenerateMenu(null);
    };

    if (showRegenerateMenu) {
      // 使用 setTimeout 延迟添加监听器，避免立即触发
      const timer = setTimeout(() => {
        document.addEventListener('mousedown', handleClickOutside);
      }, 0);
      return () => {
        clearTimeout(timer);
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [showRegenerateMenu]);

  // 加载历史会话
  useEffect(() => {
    loadChatSessions();
  }, [loadChatSessions]);

  // ✅ 会话恢复的统一处理函数（必须在 useEffect 之前定义）
  const handleSessionRestore = useCallback(async (session: any, sessionId: string) => {
    // ✅ 移除强制跳转逻辑，允许用户在任何页面查看任何会话
    // 这样提供更大的灵活性，用户可以自由选择在哪里查看会话

    // 切换会话时清空折叠状态
    setCollapsedThinking(new Set());

    if (session?.config) {
      // ✅ 恢复完整的会话配置
      const config = session.config;

      // 恢复知识库选择
      if (config.kbIds && config.kbIds.length > 0) {
        setSelectedKBs(config.kbIds);
        
        // 恢复 docToKbMap：加载知识库的文档列表
        const newDocToKbMap: Record<string, string> = {};
        const newKbDocuments: Record<string, any[]> = {};
        
        for (const kbId of config.kbIds) {
          try {
            const response = await api.listDocuments(kbId, 1, 100);
            newKbDocuments[kbId] = response.items || [];
            (response.items || []).forEach((doc: any) => {
              newDocToKbMap[doc.id] = kbId;
            });
          } catch (error) {
            console.error(`Failed to load documents for kb ${kbId}:`, error);
          }
        }
        
        setKbDocuments(prev => ({ ...prev, ...newKbDocuments }));
        setDocToKbMap(prev => ({ ...prev, ...newDocToKbMap }));
      } else {
        setSelectedKBs([]);
      }

      // ✅ 恢复文档选择
      if (config.docIds && config.docIds.length > 0) {
        setSelectedDocIds(config.docIds);
      } else {
        setSelectedDocIds([]);
      }

      // 恢复联网搜索状态
      setWebSearch(config.allowWebSearch === true);

      // ✅ 深度思考始终开启（不再从配置恢复）
      setDeepThinking(true);

      // 恢复锁定状态
      if (config.isKBLocked !== undefined) {
        setIsKBLocked(config.isKBLocked);
      } else {
        setIsKBLocked(false);
      }
    } else {
      // ✅ 如果没有配置，重置所有状态
      setSelectedKBs([]);
      setSelectedDocIds([]);
      setWebSearch(false);
      setDeepThinking(true);  // 深度思考始终开启
      setIsKBLocked(false);
    }

    setCurrentSessionId(sessionId);

    // 注意：不在这里清除 URL 参数，统一在调用方（useEffect）中处理
    // 避免重复调用 setSearchParams
  }, [navigate]);
  // ✅ 修复：移除 setSearchParams 依赖，避免重复调用

  // ✅ 处理联网搜索开关切换
  const handleWebSearchToggle = useCallback(async () => {
    const newValue = !webSearch;
    setWebSearch(newValue);

    // 如果有当前会话，更新数据库配置
    if (currentSessionId) {
      try {
        await api.updateChatSessionConfig(currentSessionId, {
          allowWebSearch: newValue
        });
        console.log(`已更新会话 ${currentSessionId} 的 allowWebSearch 配置为: ${newValue}`);
      } catch (error) {
        console.error('Failed to update session config:', error);
        toast.error('配置保存失败');
        // 回滚状态
        setWebSearch(!newValue);
      }
    }
  }, [webSearch, currentSessionId, toast]);

  // 处理知识库选择变化的回调
  const handleKBSelectionChange = useCallback((selection: SelectionState) => {
    setSelectedKBs(selection.selectedKBs);
    setSelectedDocIds(selection.selectedDocIds);
    setDocToKbMap(selection.docToKbMap);
  }, []);

  // ✅ 统一的会话恢复逻辑：优先处理 URL 参数，然后处理 localStorage
  useEffect(() => {
    if (chatSessions.length === 0) return;

    const chatIdFromUrl = searchParams.get('chatId');

    // ✅ 优先级1：处理 URL 参数中的 chatId（总是处理，不受 hasRestoredSession 限制）
    if (chatIdFromUrl) {
      if (chatIdFromUrl !== currentSessionId) {
        const session = chatSessions.find(s => s.id === chatIdFromUrl);

        if (session) {
          // 处理会话恢复逻辑（包括智能跳转）
          handleSessionRestore(session, chatIdFromUrl);
        } else {
          console.warn(`URL 参数中的会话 ${chatIdFromUrl} 不存在`);
        }

        // ✅ 清除 URL 参数，保持 URL 干净（统一在这里处理）
        setSearchParams({});
      }
      return; // URL 参数处理完毕，不再处理 localStorage
    }

    // ✅ 优先级2：从 localStorage 恢复最后活跃的会话（只在首次加载时执行）
    if (!hasRestoredSession) {
      try {
        const savedSessionId = localStorage.getItem('home_last_session_id');
        if (savedSessionId) {
          const session = chatSessions.find(s => s.id === savedSessionId);
          if (session) {
            // 验证会话确实存在且属于首页
            if (!session.config?.sourceType || session.config.sourceType === 'home') {
              handleSessionRestore(session, savedSessionId);
            } else {
              // 如果保存的会话不属于首页，清除 localStorage
              try {
                localStorage.removeItem('home_last_session_id');
              } catch (error) {
                console.error('Failed to remove invalid session from localStorage:', error);
              }
            }
          } else {
            // 如果会话不存在，清除 localStorage
            try {
              localStorage.removeItem('home_last_session_id');
            } catch (error) {
              console.error('Failed to remove non-existent session from localStorage:', error);
            }
          }
        }
      } catch (error) {
        console.error('Failed to restore session from localStorage:', error);
      }

      setHasRestoredSession(true);
    }
  }, [chatSessions.length, hasRestoredSession, handleSessionRestore, searchParams, setSearchParams, currentSessionId]);
  // ✅ 修复：URL 参数总是处理，localStorage 只在首次加载时处理
  // - searchParams: 响应 URL 参数变化，支持从其他页面跳转回来
  // - currentSessionId: 避免重复恢复同一个会话
  // - hasRestoredSession: 保护 localStorage 恢复只执行一次

  // 历史消息加载完成后的处理：自动折叠思考并滚动到底部
  useEffect(() => {
    // 当历史消息加载完成时（有会话ID，不在加载中，有消息，不在流式传输中）
    if (currentSessionId && !isLoading && messages.length > 0 && !isStreaming) {
      // 找到所有已完成的AI消息（有thinking和content的assistant消息）
      const completedAIMessages = messages.filter(msg =>
        msg.role === 'assistant' && msg.thinking && msg.content
      );

      // 将这些消息的ID添加到collapsedThinking Set中，使其默认折叠
      if (completedAIMessages.length > 0) {
        setCollapsedThinking(prev => {
          const newSet = new Set(prev);
          completedAIMessages.forEach(msg => newSet.add(msg.id));
          return newSet;
        });
      }

      // 使用 requestAnimationFrame 确保 DOM 完全渲染后再滚动
      // 双重 RAF 确保布局计算完成
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        });
      });
    }
  }, [currentSessionId, isLoading, messages.length, isStreaming]);

  // 自动滚动到最新消息 - 优化版本
  useEffect(() => {
    // 如果正在切换思考内容的折叠状态，暂停自动滚动
    if (isTogglingThinking) return;
    
    // 只在流式传输时才自动滚动，且使用 requestAnimationFrame 防抖
    if (isStreaming && shouldAutoScrollRef.current && messagesEndRef.current) {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
      });
    }
  }, [messages, isStreaming, isTogglingThinking]);

  const handleSend = async () => {
    if (!inputMessage.trim() || isStreaming) return;
    
    // 如果有附件但未全部准备好
    const hasUnreadyFiles = attachedFiles.some(f => f.status !== 'ready' && f.status !== 'error');
    if (hasUnreadyFiles) {
      toast.warning('请等待所有文件解析完成');
      return;
    }

    shouldAutoScrollRef.current = true; // 强制滚动
    
    // ✅ 如果是已有会话，在发送消息前同步更新会话配置（确保文档选择被保存）
    if (currentSessionId && (selectedKBs.length > 0 || selectedDocIds.length > 0)) {
      try {
        await api.updateChatSessionConfig(currentSessionId, {
          kbIds: selectedKBs,
          docIds: selectedDocIds,
          isKBLocked: true
        });
        console.log('📝 已同步更新会话配置');
      } catch (error) {
        console.error('Failed to update session config:', error);
        // 继续发送消息，不阻塞用户操作
      }
    }
    
    sendMessage(inputMessage, selectedModeType);
    setInputMessage('');
    
    // 发送后清除附件状态
    if (attachedFiles.length > 0) {
      setAttachedFiles([]);
    }
    
    // 🔒 如果选择了知识库且还未锁定，发送第一条消息后锁定
    if (selectedKBs.length > 0 && !isKBLocked) {
      setIsKBLocked(true);
      console.log('🔒 知识库配置已锁定');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isStreaming) {
      e.preventDefault();
      handleSend();
    }
  };

  // ✅ 新建对话 - 完整的状态清理
  const handleNewChat = () => {
    const oldSessionId = currentSessionId;

    setCurrentSessionId(undefined);
    // 清除 localStorage 中的会话ID
    try {
      localStorage.removeItem('home_last_session_id');
    } catch (error) {
      console.error('Failed to remove session ID from localStorage:', error);
    }
    clearMessages();
    setCollapsedThinking(new Set());
    setIsKBLocked(false);
    setSelectedKBs([]);

    // ✅ 重置所有会话相关状态到默认值
    setSelectedDocIds([]);
    setDocToKbMap({});
    setWebSearch(false);
    setDeepThinking(true);  // 深度思考始终开启
    setSelectedModeType(undefined);

    // ✅ 重置消息反馈状态
    setLikedMessages(new Set());
    setDislikedMessages(new Set());
    setSavedToNotes(new Set());

    // 清除 URL 参数
    setSearchParams({});

    if (oldSessionId) {
      console.debug(`Started new chat, cleared previous session: ${oldSessionId}`);
    }
  };

  // 选择历史会话
  const handleSelectChat = (chatId: string) => {
    if (chatId !== currentSessionId) {
      // 保存到 localStorage
      try {
        localStorage.setItem('home_last_session_id', chatId);
      } catch (error) {
        console.error('Failed to save session ID to localStorage:', error);
      }

      // ✅ 复用 handleSessionRestore 逻辑，确保所有配置都被正确恢复
      const session = chatSessions.find(s => s.id === chatId);
      if (session) {
        handleSessionRestore(session, chatId);
      } else {
        // 如果会话不存在（理论上不应该发生），至少切换会话ID
        setCurrentSessionId(chatId);
      }
    }
    // 清除 URL 参数
    setSearchParams({});
  };

  // 删除会话
  const handleDeleteChat = async (chatId: string) => {
    try {
      await api.deleteChatSession(chatId);
      // 如果删除的是当前会话，切换到新对话
      if (chatId === currentSessionId) {
        handleNewChat();
      }
      // 重新加载会话列表
      await loadChatSessions();
      toast.success('对话已删除');
    } catch (error) {
      console.error('Failed to delete chat:', error);
      toast.error('删除对话失败');
    }
  };

  // 复制消息内容
  const handleCopyMessage = async (content: string, messageId: string) => {
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
      // 显示复制成功状态
      setCopiedMessages(prev => new Set(prev).add(messageId));
      // 2秒后恢复
      setTimeout(() => {
        setCopiedMessages(prev => {
          const newSet = new Set(prev);
          newSet.delete(messageId);
          return newSet;
        });
      }, 2000);
    } catch (err) {
      console.error('复制失败:', err);
      toast.error('复制失败，请重试');
    }
  };

  // 点赞消息
  const handleLikeMessage = (messageId: string) => {
    setLikedMessages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
        // 如果之前点踩了，取消点踩
        setDislikedMessages(prev => {
          const newDisliked = new Set(prev);
          newDisliked.delete(messageId);
          return newDisliked;
        });
      }
      return newSet;
    });
    // TODO: 发送到后端记录
  };

  // 点踩消息
  const handleDislikeMessage = (messageId: string) => {
    setDislikedMessages(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
        // 如果之前点赞了，取消点赞
        setLikedMessages(prev => {
          const newLiked = new Set(prev);
          newLiked.delete(messageId);
          return newLiked;
        });
      }
      return newSet;
    });
    // TODO: 发送到后端记录
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
    // 标记正在切换，暂停自动滚动
    setIsTogglingThinking(true);
    
    setCollapsedThinking(prev => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
    
    // 300ms 后恢复自动滚动（等待 DOM 高度稳定）
    setTimeout(() => {
      setIsTogglingThinking(false);
    }, 300);
  };

  return (
    <div className={styles.home}>
      {isMobile && isSidebarOpen && (
        <div className={styles.overlay} onClick={() => setIsSidebarOpen(false)} />
      )}
      
      <div className={`${styles.sidebarContainer} ${isMobile && isSidebarOpen ? styles.open : ''}`}>
        <Sidebar
          onNewChat={handleNewChat}
          onSelectChat={handleSelectChat}
          onDeleteChat={handleDeleteChat}
          onClearAllChats={async () => {
            // 立即清空会话列表，提供即时反馈
            setChatSessions([]);
            handleNewChat();
            // 重新加载会话列表（应该为空）
            await loadChatSessions();
          }}
          selectedChatId={currentSessionId}
          chats={chatSessions}
        />
      </div>

      <div className={styles.mainContent}>
        {isMobile && (
          <div className={styles.mobileHeader}>
            <button onClick={() => setIsSidebarOpen(true)} className={styles.menuButton}>
              <Menu size={20} />
            </button>
            <h1 className={styles.mobileTitle}>Reader</h1>
          </div>
        )}
        
        <div className={styles.chatContainer}>
          {isLoading ? (
            // 加载历史消息
            <div className={styles.loadingContainer}>
              <div className={styles.loadingSpinner}></div>
              <p className={styles.loadingText}>加载历史消息...</p>
            </div>
          ) : messages.length === 0 ? (
            // 欢迎屏幕 + 居中布局 (Centered Layout - Polished)
            <div className={styles.emptyContainer}>
              <div className={styles.welcomeContent}>
                <h1 className={styles.welcomeTitle}>
                  <span className={styles.titleText}>用</span>
                  <span className={styles.highlight}>提问</span>
                  <span className={styles.titleText}>发现世界</span>
                </h1>
              </div>

              <div className={styles.inputSection}>
                <div className={styles.inputWrapper}>
                  {/* 任务类型卡片 - 居中网格 */}
                  <div className={styles.taskTypeGrid}>
                    {TASK_TYPE_OPTIONS.map((option) => (
                      <button
                        key={option.value || 'auto'}
                        className={`${styles.taskTypeCard} ${selectedModeType === option.value ? styles.active : ''} ${styles[option.color]}`}
                        onClick={() => setSelectedModeType(selectedModeType === option.value ? undefined : option.value)}
                        disabled={isStreaming}
                      >
                        <div className={styles.cardGlow} />
                        <div className={styles.cardContent}>
                          <div className={styles.iconBox}>
                          <option.icon size={24} strokeWidth={1.5} />
                        </div>
                          <div className={styles.cardText}>
                            <span className={styles.cardTitle}>{option.label}</span>
                            <span className={styles.cardDesc}>{option.desc}</span>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className={styles.inputBox}>
                    {/* 文件附件卡片 */}
                    {attachedFiles.length > 0 && (
                      <div className={styles.attachedFileContainer}>
                        <div className={styles.fileCardList}>
                          {attachedFiles.map((attachedFile, index) => (
                            <div key={index} className={styles.fileCard}>
                              <div className={styles.fileIcon}>
                                <img src={getFileIcon(attachedFile.file.name)} alt="File" />
                              </div>
                              <div className={styles.fileInfo}>
                                <div className={styles.fileName} title={attachedFile.file.name}>
                                  {attachedFile.file.name}
                                </div>
                                <div className={styles.fileMeta}>
                                  {formatFileSize(attachedFile.file.size)}
                                  {attachedFile.status === 'uploading' && <span className={styles.statusText}> · 上传中...</span>}
                                  {attachedFile.status === 'parsing' && <span className={styles.statusText}> · 解析中...</span>}
                                  {attachedFile.status === 'error' && <span className={styles.errorText}> · 失败</span>}
                                </div>
                              </div>
                              <button 
                                className={styles.removeFileButton}
                                onClick={(e) => { e.stopPropagation(); handleRemoveFile(index); }}
                                title="移除文件"
                              >
                                <X size={16} />
                              </button>
                              
                              {/* 进度条动画 */}
                              {(attachedFile.status === 'uploading' || attachedFile.status === 'parsing') && (
                                <div className={styles.progressLine} />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className={styles.inputRow}>
                      {selectedModeType && (() => {
                        const option = TASK_TYPE_OPTIONS.find(opt => opt.value === selectedModeType);
                        return option ? (
                          <div className={`${styles.modeBadge} ${styles[option.color]}`}>
                            {option.label}
                          </div>
                        ) : null;
                      })()}
                      <textarea
                        className={styles.input}
                        placeholder="输入您的问题..."
                        value={inputMessage}
                        onChange={(e) => setInputMessage(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isStreaming}
                        rows={1}
                        style={{
                          height: 'auto',
                          minHeight: '24px',
                          maxHeight: '200px'
                        }}
                        onInput={(e) => {
                          const target = e.target as HTMLTextAreaElement;
                          target.style.height = 'auto';
                          target.style.height = target.scrollHeight + 'px';
                        }}
                      />
                      <div className={styles.inputActions}>
                        <input
                          type="file"
                          ref={fileInputRef}
                          style={{ display: 'none' }}
                          accept=".pdf,.txt,.md,.doc,.docx"
                          multiple
                          onChange={handleFileSelect}
                          disabled={isStreaming || attachedFiles.length >= MAX_FILES}
                        />
                        <button
                          className={styles.uploadButton}
                          onClick={handleUploadClick}
                          disabled={isStreaming || attachedFiles.length >= MAX_FILES}
                          title={`上传文件 (PDF, TXT, MD, DOC, DOCX) - 最多${MAX_FILES}个`}
                        >
                          <Paperclip size={20} />
                        </button>
                        <SendStopButton
                          isStreaming={isStreaming}
                          disabled={attachedFiles.length > 0 && attachedFiles.some(f => f.status !== 'ready' && f.status !== 'error')}
                          onSend={handleSend}
                          onStop={stopGeneration}
                          hasContent={!!inputMessage.trim()}
                        />
                      </div>
                    </div>

                    <div className={styles.modeSwitch}>
                      <button
                        className={`${styles.modeButton} ${webSearch ? styles.active : ''}`}
                        onClick={handleWebSearchToggle}
                        disabled={isStreaming}
                        title="联网搜索：获取实时信息"
                      >
                        <Search size={16} />
                        <span>联网搜索</span>
                      </button>
                      <div className={styles.kbSelectorWrapper}>
                        <button
                          ref={kbButtonRef}
                          className={`${styles.modeButton} ${selectedKBs.length > 0 ? styles.active : ''} ${isKBLocked ? styles.readonly : ''}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenKBSelector(kbButtonRef);
                          }}
                          onMouseDown={(e) => {
                            e.stopPropagation();
                          }}
                          disabled={isStreaming}
                          title={isKBLocked ? "查看当前会话使用的知识库（只读）" : "选择知识库"}
                        >
                          <Database size={16} />
                          <span>知识库{selectedDocIds.length > 0 && ` (${selectedDocIds.length})`}</span>
                        </button>
                        
                        <KnowledgeBaseSelector
                          selectedKBs={selectedKBs}
                          selectedDocIds={selectedDocIds}
                          docToKbMap={docToKbMap}
                          onSelectionChange={handleKBSelectionChange}
                          isOpen={showKBSelector}
                          onClose={() => setShowKBSelector(false)}
                          position={kbPanelPosition || undefined}
                          disabled={isKBLocked}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            // 对话界面
            <>
              {/* 计算是否有双栏布局激活（最后一条AI消息使用双栏） */}
              {(() => {
                const lastAIMessage = messages.filter(m => m.role === 'assistant').slice(-1)[0];
                const isDualLayoutActive = lastAIMessage && shouldUseDualLayout(documentProgress, lastAIMessage, isStreaming, totalDocCount);
                return (
              <div 
                className={`${styles.messagesArea} ${isDualLayoutActive ? styles.dualLayoutActive : ''}`}
                ref={chatContainerRef}
                onScroll={handleScroll}
              >
                <div className={styles.messageGroup}>
                  {messages.map((msg, index) => {
                    const isThisMessageDualLayout = msg.role === 'assistant' && index === messages.length - 1 && shouldUseDualLayout(documentProgress, msg, isStreaming, totalDocCount);
                    return (
                    <div key={msg.id} className={`${styles.messageItem} ${msg.role === 'user' ? styles.userMessageItem : styles.aiMessageItem} ${isThisMessageDualLayout ? styles.dualLayoutMessage : ''}`}>
                      <div className={msg.role === 'user' ? styles.userAvatar : styles.aiAvatar}>
                        {msg.role === 'user' ? (
                          profile?.avatar ? (
                            <img src={profile.avatar} alt="User" className={styles.avatarImage} />
                          ) : (
                            <User size={18} />
                          )
                        ) : (
                          <img src={aiAvatarUrl} alt="AI" className={styles.avatarImage} />
                        )}
                      </div>
                      <div className={styles.messageContent}>
                        {/* 如果是 AI 消息且内容和思考都为空且正在流式传输（最后一条消息），显示思考动画（排除多文档任务和文档总结阶段） */}
                        {msg.role === 'assistant' && !msg.content && !msg.thinking && isStreaming && index === messages.length - 1 && !shouldUseDualLayout(documentProgress, msg, isStreaming, totalDocCount) && documentProgress.size === 0 ? (
                          <div className={styles.thinking}>
                            <div className={styles.thinkingDots}>
                              <span className={styles.dot}></span>
                              <span className={styles.dot}></span>
                              <span className={styles.dot}></span>
                            </div>
                            <span className={styles.thinkingText}>正在思考...</span>
                          </div>
                        ) : msg.role === 'assistant' && index === messages.length - 1 && shouldUseDualLayout(documentProgress, msg, isStreaming, totalDocCount) ? (
                          /* 双栏布局：多文档任务时使用 */
                          (() => {
                            console.log(`[Home] Rendering DualColumnLayout, hasContent=${!!msg.content}, hasThinking=${!!msg.thinking}, docProgress=${documentProgress.size}`);
                            return (
                          <>
                            <DualColumnLayout
                              message={msg}
                              isStreaming={isStreaming}
                              documentProgress={documentProgress}
                              isLastMessage={index === messages.length - 1}
                            />
                            {/* AI 消息操作按钮 - 只在流式输出完成后显示 */}
                            {msg.content && !isStreaming && (
                              <div className={styles.messageActions}>
                                <Tooltip content={copiedMessages.has(msg.id) ? "已复制" : "复制"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${copiedMessages.has(msg.id) ? styles.copied : ''}`}
                                    onClick={() => handleCopyMessage(msg.content, msg.id)}
                                  >
                                    {copiedMessages.has(msg.id) ? <Check size={16} /> : <Copy size={16} />}
                                  </button>
                                </Tooltip>
                                <Tooltip content={likedMessages.has(msg.id) ? "取消点赞" : "点赞"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${likedMessages.has(msg.id) ? styles.liked : ''}`}
                                    onClick={() => handleLikeMessage(msg.id)}
                                  >
                                    <ThumbsUp size={16} />
                                  </button>
                                </Tooltip>
                                <Tooltip content={dislikedMessages.has(msg.id) ? "取消点踩" : "点踩"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${dislikedMessages.has(msg.id) ? styles.disliked : ''}`}
                                    onClick={() => handleDislikeMessage(msg.id)}
                                  >
                                    <ThumbsDown size={16} />
                                  </button>
                                </Tooltip>
                                <Tooltip content={savedToNotes.has(msg.id) ? "已保存到笔记" : "保存到笔记"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${savedToNotes.has(msg.id) ? styles.saved : ''}`}
                                    onClick={() => handleSaveToNotes(msg.id)}
                                  >
                                    <FileText size={16} />
                                  </button>
                                </Tooltip>
                                <div className={styles.regenerateWrapper}>
                                  <Tooltip content="重新生成" position="top">
                                    <button
                                      className={styles.actionButton}
                                      onClick={() => regenerateLastMessage()}
                                      onContextMenu={(e) => {
                                        e.preventDefault();
                                        setShowRegenerateMenu(showRegenerateMenu === msg.id ? null : msg.id);
                                      }}
                                    >
                                      <RefreshCw size={16} />
                                    </button>
                                  </Tooltip>
                                  {showRegenerateMenu === msg.id && (
                                    <div className={styles.regenerateMenu} ref={regenerateMenuRef}>
                                      <button
                                        className={styles.regenerateMenuItem}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          regenerateLastMessage();
                                          setShowRegenerateMenu(null);
                                        }}
                                      >
                                        <RefreshCw size={14} />
                                        <span>重新生成</span>
                                      </button>
                                      <button
                                        className={styles.regenerateMenuItem}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          regenerateLastMessage(true);
                                          setShowRegenerateMenu(null);
                                        }}
                                        title="重新生成文档总结并刷新缓存"
                                      >
                                        <Database size={14} />
                                        <span>刷新缓存重新生成</span>
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </>
                            );
                          })()
                        ) : (
                          <>
                            {/* 单栏布局：普通消息 */}
                            {/* 文档总结进度（多文档任务且最后一条消息） */}
                            {msg.role === 'assistant' && index === messages.length - 1 && documentProgress.size > 0 && (
                              <div style={{ marginBottom: '16px' }}>
                                <DocumentProgress 
                                  documents={Array.from(documentProgress.values())}
                                  isStreaming={isStreaming}
                                />
                              </div>
                            )}
                            
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
                                  </div>
                                )}
                              </div>
                            )}
                            
                            {/* 如果思考完成但答案未到达，显示生成提示 */}
                            {msg.role === 'assistant' && msg.thinking && !msg.content && isStreaming && index === messages.length - 1 && (
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
                              <div className={msg.role === 'user' ? styles.userMessageText : styles.aiMessageText}>
                                {msg.role === 'user' ? (
                                  msg.content
                                ) : (
                                  <OptimizedMarkdown>
                                    {msg.content}
                                  </OptimizedMarkdown>
                                )}
                              </div>
                            )}
                            {/* AI 消息操作按钮 - 只在流式输出完成后显示 */}
                            {msg.role === 'assistant' && msg.content && (!isStreaming || index !== messages.length - 1) && (
                              <div className={styles.messageActions}>
                                <Tooltip content={copiedMessages.has(msg.id) ? "已复制" : "复制"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${copiedMessages.has(msg.id) ? styles.copied : ''}`}
                                    onClick={() => handleCopyMessage(msg.content, msg.id)}
                                  >
                                    {copiedMessages.has(msg.id) ? <Check size={16} /> : <Copy size={16} />}
                                  </button>
                                </Tooltip>
                                <Tooltip content={likedMessages.has(msg.id) ? "取消点赞" : "点赞"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${likedMessages.has(msg.id) ? styles.liked : ''}`}
                                    onClick={() => handleLikeMessage(msg.id)}
                                  >
                                    <ThumbsUp size={16} />
                                  </button>
                                </Tooltip>
                                <Tooltip content={dislikedMessages.has(msg.id) ? "取消点踩" : "点踩"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${dislikedMessages.has(msg.id) ? styles.disliked : ''}`}
                                    onClick={() => handleDislikeMessage(msg.id)}
                                  >
                                    <ThumbsDown size={16} />
                                  </button>
                                </Tooltip>
                                <Tooltip content={savedToNotes.has(msg.id) ? "已保存到笔记" : "保存到笔记"} position="top">
                                  <button
                                    className={`${styles.actionButton} ${savedToNotes.has(msg.id) ? styles.saved : ''}`}
                                    onClick={() => handleSaveToNotes(msg.id)}
                                  >
                                    <FileText size={16} />
                                  </button>
                                </Tooltip>
                                <div className={styles.regenerateWrapper}>
                                  <Tooltip content="重新生成" position="top">
                                    <button
                                      className={styles.actionButton}
                                      onClick={() => regenerateLastMessage()}
                                      onContextMenu={(e) => {
                                        e.preventDefault();
                                        setShowRegenerateMenu(showRegenerateMenu === msg.id ? null : msg.id);
                                      }}
                                    >
                                      <RefreshCw size={16} />
                                    </button>
                                  </Tooltip>
                                  {showRegenerateMenu === msg.id && (
                                    <div className={styles.regenerateMenu} ref={regenerateMenuRef}>
                                      <button
                                        className={styles.regenerateMenuItem}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          regenerateLastMessage();
                                          setShowRegenerateMenu(null);
                                        }}
                                      >
                                        <RefreshCw size={14} />
                                        <span>重新生成</span>
                                      </button>
                                      <button
                                        className={styles.regenerateMenuItem}
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          regenerateLastMessage(true);
                                          setShowRegenerateMenu(null);
                                        }}
                                        title="重新生成文档总结并刷新缓存"
                                      >
                                        <Database size={14} />
                                        <span>刷新缓存重新生成</span>
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  );
                  })}
                  <div ref={messagesEndRef} />
                </div>
              </div>
                );
              })()}

              <div className={styles.inputSection}>
                <div className={styles.inputWrapper}>
                  <div className={styles.inputBox}>
                    {/* 文件附件卡片 */}
                    {attachedFiles.length > 0 && (
                      <div className={styles.attachedFileContainer}>
                        <div className={styles.fileCardList}>
                          {attachedFiles.map((attachedFile, index) => (
                            <div key={index} className={styles.fileCard}>
                              <div className={styles.fileIcon}>
                                <img src={getFileIcon(attachedFile.file.name)} alt="File" />
                              </div>
                              <div className={styles.fileInfo}>
                                <div className={styles.fileName} title={attachedFile.file.name}>
                                  {attachedFile.file.name}
                                </div>
                                <div className={styles.fileMeta}>
                                  {formatFileSize(attachedFile.file.size)}
                                  {attachedFile.status === 'uploading' && <span className={styles.statusText}> · 上传中...</span>}
                                  {attachedFile.status === 'parsing' && <span className={styles.statusText}> · 解析中...</span>}
                                  {attachedFile.status === 'error' && <span className={styles.errorText}> · 失败</span>}
                                </div>
                              </div>
                              <button 
                                className={styles.removeFileButton}
                                onClick={(e) => { e.stopPropagation(); handleRemoveFile(index); }}
                                title="移除文件"
                              >
                                <X size={16} />
                              </button>
                              
                              {/* 进度条动画 */}
                              {(attachedFile.status === 'uploading' || attachedFile.status === 'parsing') && (
                                <div className={styles.progressLine} />
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className={styles.inputRow}>
                      {selectedModeType && (() => {
                        const option = TASK_TYPE_OPTIONS.find(opt => opt.value === selectedModeType);
                        return option ? (
                          <div className={`${styles.modeBadge} ${styles[option.color]}`}>
                            {option.label}
                          </div>
                        ) : null;
                      })()}
                      <textarea
                        className={styles.input}
                        placeholder="继续对话..."
                        value={inputMessage}
                        onChange={(e) => setInputMessage(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={isStreaming}
                        rows={1}
                        style={{
                          height: 'auto',
                          minHeight: '24px',
                          maxHeight: '200px'
                        }}
                        onInput={(e) => {
                          const target = e.target as HTMLTextAreaElement;
                          target.style.height = 'auto';
                          target.style.height = target.scrollHeight + 'px';
                        }}
                      />
                      <div className={styles.inputActions}>
                        <input
                          type="file"
                          ref={fileInputRef}
                          style={{ display: 'none' }}
                          accept=".pdf,.txt,.md,.doc,.docx"
                          multiple
                          onChange={handleFileSelect}
                          disabled={isStreaming || attachedFiles.length >= MAX_FILES}
                        />
                        <button
                          className={styles.uploadButton}
                          onClick={handleUploadClick}
                          disabled={isStreaming || attachedFiles.length >= MAX_FILES}
                          title={`上传文件 (PDF, TXT, MD, DOC, DOCX) - 最多${MAX_FILES}个`}
                        >
                          <Paperclip size={20} />
                        </button>
                        <SendStopButton
                          isStreaming={isStreaming}
                          disabled={attachedFiles.length > 0 && attachedFiles.some(f => f.status !== 'ready' && f.status !== 'error')}
                          onSend={handleSend}
                          onStop={stopGeneration}
                          hasContent={!!inputMessage.trim()}
                        />
                      </div>
                    </div>

                    <div className={styles.modeSwitch}>
                      <button
                        className={`${styles.modeButton} ${webSearch ? styles.active : ''}`}
                        onClick={handleWebSearchToggle}
                        disabled={isStreaming}
                        title="联网搜索：获取实时信息"
                      >
                        <Search size={16} />
                        <span>联网搜索</span>
                      </button>
                      <div className={`${styles.kbSelectorWrapper} ${styles.kbSelectorWrapperTop}`}>
                        <button
                          ref={kbButtonRef2}
                          className={`${styles.modeButton} ${selectedKBs.length > 0 ? styles.active : ''} ${isKBLocked ? styles.readonly : ''}`}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenKBSelector(kbButtonRef2);
                          }}
                          onMouseDown={(e) => {
                            e.stopPropagation();
                          }}
                          disabled={isStreaming}
                          title={isKBLocked ? "查看当前会话使用的知识库（只读）" : "选择知识库"}
                        >
                          <Database size={16} />
                          <span>知识库{selectedDocIds.length > 0 && ` (${selectedDocIds.length})`}</span>
                        </button>
                        
                        <KnowledgeBaseSelector
                          selectedKBs={selectedKBs}
                          selectedDocIds={selectedDocIds}
                          docToKbMap={docToKbMap}
                          onSelectionChange={handleKBSelectionChange}
                          isOpen={showKBSelector}
                          onClose={() => setShowKBSelector(false)}
                          position={kbPanelPosition || undefined}
                          disabled={isKBLocked}
                        />
                      </div>
                    </div>
                  </div>
                  
                  <div className={styles.disclaimer}>
                    答案由AI生成，仅供参考
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
