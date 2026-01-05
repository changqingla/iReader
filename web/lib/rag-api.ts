import { API_BASE_URL } from './api';

interface ChatRequest {
  kb_id?: string;
  doc_ids?: string[];
  message: string;
  session_id: string;
  mode: 'deep' | 'search';
  enable_web_search?: boolean;
  show_thinking?: boolean;  // 是否显示思考过程（深度思考模式）
  mode_type?: string;  // 任务类型（可选）
  refresh_summary_cache?: boolean;  // 是否强制刷新文档总结缓存（多文档总结模式）
}

// 文档总结进度数据结构
interface DocSummaryInitData {
  total: number;
  cached: number;
  to_generate: number;
}

interface DocSummaryStartData {
  doc_id: string;
  doc_name: string;
  index: number;
  total: number;
}

interface DocSummaryChunkData {
  doc_id: string;
  content: string;
}

interface DocSummaryCompleteData {
  doc_id: string;
  doc_name: string;
  summary: string;
  from_cache: boolean;
  index: number;
  total: number;
}

interface StreamChatOptions extends ChatRequest {
  onToken: (token: string) => void;
  onThinking: (thinking: string) => void;
  onError: (error: string) => void;
  onDone: () => void;
  onFollowUpQuestion?: (question: string, index: number) => void;
  onFinalAnswer?: (data: {
    answer: string;
    session_id: string;
    follow_up_questions: string[];
    detected_intent: string;
  }) => void;
  // 文档总结进度回调
  onDocSummaryInit?: (data: DocSummaryInitData) => void;
  onDocSummaryStart?: (data: DocSummaryStartData) => void;
  onDocSummaryChunk?: (data: DocSummaryChunkData) => void;
  onDocSummaryComplete?: (data: DocSummaryCompleteData) => void;
  // 中止信号
  signal?: AbortSignal;
}

class RAGAPIClient {
  private baseURL: string;

  constructor() {
    this.baseURL = API_BASE_URL;
  }

  /**
   * Stream chat with RAG service
   */
  async streamChat(options: StreamChatOptions): Promise<void> {
    const { 
      onToken, 
      onThinking, 
      onError, 
      onDone, 
      onFollowUpQuestion, 
      onFinalAnswer,
      onDocSummaryInit,
      onDocSummaryStart,
      onDocSummaryChunk,
      onDocSummaryComplete,
      signal,
      ...request 
    } = options;

    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${this.baseURL}/rag/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(request),
        signal // 传递中止信号
      });

      if (!response.ok) {
        // 处理401 Unauthorized错误（Token过期）
        if (response.status === 401) {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('userProfile');
          setTimeout(() => {
            window.location.href = '/auth';
          }, 1500);
          throw new Error('当前登录已过期，请重新登录');
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim() || !line.startsWith('data: ')) continue;
          
          const data = line.slice(6); // Remove "data: " prefix
          
          if (data === '[DONE]') {
            onDone();
            return;
          }

          try {
            const chunk = JSON.parse(data);

            switch (chunk.type) {
              case 'token':
                onToken(chunk.content);
                break;
              case 'thinking':
                onThinking(chunk.content);
                break;
              case 'follow_up_question':
                if (onFollowUpQuestion) {
                  const fqData = JSON.parse(chunk.content);
                  onFollowUpQuestion(fqData.question, fqData.index);
                }
                break;
              case 'final_answer':
                if (onFinalAnswer) {
                  const faData = JSON.parse(chunk.content);
                  onFinalAnswer(faData);
                }
                break;
              // 文档总结进度事件
              case 'doc_summary_init':
                if (onDocSummaryInit) {
                  const initData = JSON.parse(chunk.content);
                  onDocSummaryInit(initData);
                }
                break;
              case 'doc_summary_start':
                if (onDocSummaryStart) {
                  const startData = JSON.parse(chunk.content);
                  onDocSummaryStart(startData);
                }
                break;
              case 'doc_summary_chunk':
                if (onDocSummaryChunk) {
                  const chunkData = JSON.parse(chunk.content);
                  onDocSummaryChunk(chunkData);
                }
                break;
              case 'doc_summary_complete':
                if (onDocSummaryComplete) {
                  const completeData = JSON.parse(chunk.content);
                  onDocSummaryComplete(completeData);
                }
                break;
              case 'error':
                onError(chunk.content);
                return;
            }
          } catch (e) {
            console.warn('Failed to parse chunk:', data, e);
          }
        }
      }

      onDone();
    } catch (error) {
      // 如果是用户主动中止，不触发错误回调
      if (error instanceof DOMException && error.name === 'AbortError') {
        onDone();
        return;
      }
      onError(String(error));
    }
  }

  /**
   * Non-streaming chat (for testing)
   */
  async chat(request: ChatRequest): Promise<any> {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(`${this.baseURL}/rag/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify(request)
    });

    if (!response.ok) {
      // 处理401 Unauthorized错误（Token过期）
      if (response.status === 401) {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('userProfile');
        setTimeout(() => {
          window.location.href = '/auth';
        }, 1500);
        throw new Error('当前登录已过期，请重新登录');
      }
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Cancel an ongoing stream for a session
   * 
   * @param sessionId - The session ID to cancel
   * @returns Promise with cancellation result
   */
  async cancelStream(sessionId: string): Promise<{ success: boolean; message?: string; error?: string }> {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${this.baseURL}/rag/chat/cancel/${sessionId}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (!response.ok) {
        // 处理401 Unauthorized错误（Token过期）
        if (response.status === 401) {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('userProfile');
          setTimeout(() => {
            window.location.href = '/auth';
          }, 1500);
          throw new Error('当前登录已过期，请重新登录');
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      return response.json();
    } catch (error) {
      console.error('Failed to cancel stream:', error);
      return { success: false, error: String(error) };
    }
  }
}

export const ragAPI = new RAGAPIClient();

