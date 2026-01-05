import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, ChevronUp, FileText, Check, Loader2, Package } from 'lucide-react';
import OptimizedMarkdown from '../OptimizedMarkdown';
import styles from './DocumentProgress.module.css';

export interface DocumentSummaryProgress {
  docId: string;
  docName: string;
  status: 'pending' | 'processing' | 'completed' | 'cached' | 'error';
  summary: string;
  index: number;
  total: number;
}

interface DocumentProgressProps {
  documents: DocumentSummaryProgress[];
  isStreaming?: boolean;
}

const DocumentProgress: React.FC<DocumentProgressProps> = ({ documents }) => {
  const completed = documents.filter(d => d.status === 'completed' || d.status === 'cached');
  
  // 调试日志
  console.log(`[DocumentProgress] render with ${documents.length} docs:`, documents.map(d => ({ id: d.docId.slice(0, 8), len: d.summary.length, status: d.status })));
  
  if (documents.length === 0) {
    return null;
  }
  
  return (
    <div className={styles.documentProgress}>
      {/* 总体进度 */}
      <div className={styles.progressHeader}>
        <span className={styles.progressTitle}>
          {completed.length === documents.length 
            ? `📚 ${documents.length} 篇文档已分析完成`
            : `📚 正在分析 ${documents.length} 篇文档`
          }
        </span>
        <span className={styles.progressCount}>
          {completed.length}/{documents.length}
        </span>
      </div>
      
      {/* 进度条 */}
      <div className={styles.progressBar}>
        <div 
          className={styles.progressFill}
          style={{ width: `${(completed.length / documents.length) * 100}%` }}
        />
      </div>
      
      {/* 文档列表 */}
      <div className={styles.documentList}>
        {documents.map(doc => (
          <DocumentCard key={doc.docId} document={doc} />
        ))}
      </div>
    </div>
  );
};

const DocumentCard: React.FC<{ document: DocumentSummaryProgress }> = ({ document }) => {
  // 调试日志
  console.log(`[DocumentCard] render doc=${document.docId.slice(0, 8)}, status=${document.status}, summary_len=${document.summary.length}`);
  
  // 处理中默认展开，完成后默认折叠
  const [manualExpanded, setManualExpanded] = useState<boolean | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  
  // 计算实际展开状态：
  // - 如果用户手动操作过，使用用户的选择
  // - 否则：处理中自动展开，完成后自动折叠
  const isProcessing = document.status === 'processing';
  const autoExpanded = isProcessing; // 处理中自动展开
  const expanded = manualExpanded !== null ? manualExpanded : autoExpanded;
  
  // 流式生成时自动滚动到底部
  useEffect(() => {
    if (isProcessing && expanded && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [document.summary, isProcessing, expanded, document.docId]);
  
  const statusIcon = {
    pending: <Loader2 size={14} className={styles.pendingIcon} />,
    processing: <Loader2 size={14} className={styles.spinIcon} />,
    completed: <Check size={14} className={styles.completedIcon} />,
    cached: <Package size={14} className={styles.cachedIcon} />,
    error: <span className={styles.errorIcon}>❌</span>
  }[document.status];
  
  // 有内容就可以展开
  const canExpand = document.summary && document.summary.length > 0;
  
  const handleToggle = () => {
    if (canExpand) {
      setManualExpanded(!expanded);
    }
  };
  
  return (
    <div className={`${styles.docCard} ${styles[document.status]} ${expanded && canExpand ? styles.expanded : ''}`}>
      <div 
        className={styles.docHeader} 
        onClick={handleToggle}
        style={{ cursor: canExpand ? 'pointer' : 'default' }}
      >
        <span className={styles.statusIcon}>{statusIcon}</span>
        <FileText size={14} className={styles.fileIcon} />
        <span className={styles.docName} title={document.docName}>
          {document.docName}
        </span>
        {document.status === 'cached' && (
          <span className={styles.cacheTag}>缓存</span>
        )}
        {canExpand && (
          <span className={styles.expandIcon}>
            {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </span>
        )}
      </div>
      
      {/* 展开时显示内容 */}
      {canExpand && expanded && (
        <div className={`${styles.contentArea} ${isProcessing ? styles.streaming : ''}`}>
          <div ref={contentRef} className={styles.contentText}>
            <OptimizedMarkdown className={styles.summaryMarkdown}>
              {document.summary}
            </OptimizedMarkdown>
            {isProcessing && <span className={styles.cursor}>▌</span>}
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentProgress;
