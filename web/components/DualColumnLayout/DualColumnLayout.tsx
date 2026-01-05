import React from 'react';
import { Brain, Sparkles } from 'lucide-react';
import OptimizedMarkdown from '@/components/OptimizedMarkdown';
import DocumentProgress, { DocumentSummaryProgress } from '@/components/DocumentProgress/DocumentProgress';
import styles from './DualColumnLayout.module.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  detectedIntent?: string;
  documentSummaries?: Array<{  // 文档总结信息（从数据库加载）
    doc_id: string;
    doc_name: string;
    summary: string;
    from_cache: boolean;
  }>;
}

interface DualColumnLayoutProps {
  message: Message;
  isStreaming: boolean;
  documentProgress: Map<string, DocumentSummaryProgress>;
  isLastMessage: boolean;
}

// 从思考内容中提取文档总结（用于历史消息恢复）
function extractDocumentSummariesFromThinking(thinking: string): DocumentSummaryProgress[] {
  if (!thinking) return [];
  
  const documents: DocumentSummaryProgress[] = [];
  const seen = new Set<string>(); // 避免重复
  
  // 匹配文档总结块的模式
  // 格式1: 📄 **文档名.pdf** 总结完成
  // 格式2: 📄 **文档名.pdf** (缓存)
  const docPattern = /📄\s*\*\*([^*]+)\*\*\s*(总结完成|\(缓存\)|（缓存）)/g;
  
  let match: RegExpExecArray | null;
  while ((match = docPattern.exec(thinking)) !== null) {
    const docName = match[1].trim();
    const statusText = match[2];
    
    // 避免重复添加同一文档
    if (seen.has(docName)) continue;
    seen.add(docName);
    
    const isCached = statusText.includes('缓存');
    documents.push({
      docId: `doc-${documents.length}`,
      docName: docName,
      status: isCached ? 'cached' : 'completed',
      summary: '', // 总结内容从数据库加载
      index: documents.length,
      total: 0 // 稍后更新
    });
  }
  
  // 更新 total 字段
  documents.forEach(doc => {
    doc.total = documents.length;
  });
  
  return documents;
}

// 判断是否应该使用双栏布局
export function shouldUseDualLayout(
  documentProgress: Map<string, DocumentSummaryProgress>,
  message: Message,
  isStreaming?: boolean,
  totalDocCount?: number // 从 doc_summary_init 事件获取的总文档数量
): boolean {
  const docProgressCount = documentProgress.size;
  const docSummariesCount = message.documentSummaries?.length || 0;
  const docsFromThinking = extractDocumentSummariesFromThinking(message.thinking || '');
  const thinkingDocCount = docsFromThinking.length;
  
  const maxDocCount = Math.max(docProgressCount, docSummariesCount, thinkingDocCount, totalDocCount || 0);
  const hasMultipleDocs = maxDocCount > 1;
  
  // 🔑 优化：只有当开始生成答案内容（thinking 或 content）时才启用双栏布局
  // 纯文档总结阶段（无 thinking 和 content）不使用双栏，由单栏全宽显示文档进度
  const hasAnswerContent = (message.thinking && message.thinking.length > 0) || (message.content && message.content.length > 0);
  
  // 如果有答案内容，启用双栏；否则不使用双栏（让单栏显示文档进度）
  const result = hasMultipleDocs && hasAnswerContent;
  
  console.log(`[shouldUseDualLayout] docProgress=${docProgressCount}, totalDocCount=${totalDocCount}, isStreaming=${isStreaming}, hasThinking=${!!message.thinking}, hasContent=${!!message.content}, hasMultipleDocs=${hasMultipleDocs}, hasAnswerContent=${hasAnswerContent}, result=${result}`);
  
  return result;
}

const DualColumnLayout: React.FC<DualColumnLayoutProps> = ({
  message,
  isStreaming,
  documentProgress,
  isLastMessage
}) => {
  // 调试：记录组件渲染
  console.log(`[DualLayout] Component render, documentProgress.size=${documentProgress.size}, isStreaming=${isStreaming}`);
  
  // 获取文档列表：优先使用实时进度，其次使用数据库中的 documentSummaries，最后从 thinking 中提取
  // 🔑 关键修复：移除 useMemo，直接计算 documents，确保每次渲染都能获取最新数据
  const progressDocs = Array.from(documentProgress.values());
  console.log('[DualLayout] calculating documents:', progressDocs.map(d => ({ id: d.docId.slice(0, 8), len: d.summary.length, status: d.status })));
  
  let documents: DocumentSummaryProgress[];
  if (progressDocs.length > 0) {
    documents = progressDocs;
  } else if (message.documentSummaries && message.documentSummaries.length > 0) {
    // 使用数据库中保存的文档总结（历史消息）
    documents = message.documentSummaries.map((doc, index): DocumentSummaryProgress => ({
      docId: doc.doc_id,
      docName: doc.doc_name,
      status: doc.from_cache ? 'cached' : 'completed',
      summary: doc.summary,
      index: index,
      total: message.documentSummaries!.length
    }));
  } else {
    // 兼容旧数据：从 thinking 中提取文档信息（没有总结内容）
    documents = extractDocumentSummariesFromThinking(message.thinking || '');
  }
  
  return (
    <div className={styles.dualLayout}>
      {/* 左栏：思考过程 + 文档分析 */}
      <div className={styles.leftColumn}>
        <div className={styles.columnHeader}>
          <Brain size={16} />
          <span>思考过程</span>
        </div>
        
        {/* 思考过程内容（直接展示完整内容） */}
        {message.thinking && (
          <div className={styles.thinkingContent}>
            <OptimizedMarkdown>{message.thinking}</OptimizedMarkdown>
          </div>
        )}
        
        {/* 文档分析进度 */}
        {documents.length > 0 && (
          <div className={styles.documentAnalysis}>
            <DocumentProgress 
              documents={documents}
              isStreaming={isStreaming}
            />
          </div>
        )}
      </div>
      
      {/* 右栏：最终报告（无标题） */}
      <div className={styles.rightColumn}>
        {isStreaming && isLastMessage && (
          <div className={styles.streamingHeader}>
            <Sparkles size={12} className={styles.sparkleIcon} />
            <span>生成中</span>
          </div>
        )}
        
        <div className={styles.reportContent}>
          {message.content ? (
            <>
              <OptimizedMarkdown>
                {message.content}
              </OptimizedMarkdown>
              {isStreaming && isLastMessage && <span className={styles.cursor}>▌</span>}
            </>
          ) : (
            <div className={styles.waitingContent}>
              <div className={styles.loadingDots}>
                <span className={styles.dot}></span>
                <span className={styles.dot}></span>
                <span className={styles.dot}></span>
              </div>
              <span>正在生成报告...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DualColumnLayout;
