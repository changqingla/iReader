/**
 * 知识库侧边栏组件
 * 显示"我的知识库"和"订阅的知识库"列表
 */
import React, { useEffect, useState, useImperativeHandle, forwardRef } from 'react';
import { Plus, Database, MoreVertical, Edit2, Trash2 } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { kbAPI } from '@/lib/api';
import { getKnowledgeBaseAvatar } from '@/utils/avatarUtils';
import styles from './KnowledgeSidebar.module.css';

interface KnowledgeSidebarProps {
  knowledgeBases: any[];
  onKnowledgeBasesChange: () => void;
  onCreateClick: () => void;
  onEditClick?: (kb: any) => void;
  onDeleteClick?: (kbId: string) => void;
  onDocumentDrop?: (docId: string, sourceKbId: string, targetKbId: string) => void;
  currentKbId?: string;
}

export interface KnowledgeSidebarRef {
  refreshSubscriptions: () => Promise<void>;
}

const KnowledgeSidebar = forwardRef<KnowledgeSidebarRef, KnowledgeSidebarProps>(({
  knowledgeBases,
  onKnowledgeBasesChange: _onKnowledgeBasesChange,
  onCreateClick,
  onEditClick,
  onDeleteClick,
  onDocumentDrop,
  currentKbId
}, ref) => {
  // Note: _onKnowledgeBasesChange is kept for API compatibility but currently unused
  void _onKnowledgeBasesChange;
  
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [dragOverKbId, setDragOverKbId] = useState<string | null>(null);

  useEffect(() => {
    loadSubscriptions();

    // 监听订阅状态变化事件（用于跨页面同步）
    const handleSubscriptionChange = (e: StorageEvent) => {
      if (e.key === 'kb_subscription_changed') {
        loadSubscriptions();
      }
    };

    // 也监听自定义事件（同页面内的刷新）
    const handleCustomEvent = () => {
      loadSubscriptions();
    };

    window.addEventListener('storage', handleSubscriptionChange as any);
    window.addEventListener('kb_subscription_changed', handleCustomEvent);

    return () => {
      window.removeEventListener('storage', handleSubscriptionChange as any);
      window.removeEventListener('kb_subscription_changed', handleCustomEvent);
    };
  }, []);

  const loadSubscriptions = async () => {
    try {
      const response = await kbAPI.listSubscriptions();
      setSubscriptions(response.items);
    } catch (error) {
      console.error('Failed to load subscriptions:', error);
    }
  };

  // 暴露刷新订阅列表的方法给父组件
  useImperativeHandle(ref, () => ({
    refreshSubscriptions: loadSubscriptions
  }));

  const handleKBClick = (kbId: string) => {
    navigate(`/knowledge/${kbId}`);
    setMenuOpen(null);
  };

  const handleMenuClick = (e: React.MouseEvent, kbId: string) => {
    e.stopPropagation();
    setMenuOpen(menuOpen === kbId ? null : kbId);
  };

  const handleEdit = (e: React.MouseEvent, kb: any) => {
    e.stopPropagation();
    setMenuOpen(null);
    if (onEditClick) {
      onEditClick(kb);
    }
  };

  const handleDelete = (e: React.MouseEvent, kbId: string) => {
    e.stopPropagation();
    setMenuOpen(null);
    if (onDeleteClick) {
      onDeleteClick(kbId);
    }
  };

  const isActive = (kbId: string) => {
    return location.pathname === `/knowledge/${kbId}`;
  };

  // 拖拽处理
  const handleDragOver = (e: React.DragEvent, kbId: string) => {
    e.preventDefault();
    // 不能拖到当前知识库
    if (kbId === currentKbId) return;
    e.dataTransfer.dropEffect = 'move';
    setDragOverKbId(kbId);
  };

  const handleDragLeave = () => {
    setDragOverKbId(null);
  };

  const handleDrop = (e: React.DragEvent, targetKbId: string) => {
    e.preventDefault();
    setDragOverKbId(null);
    
    // 不能拖到当前知识库
    if (targetKbId === currentKbId) return;
    
    const docId = e.dataTransfer.getData('docId');
    const sourceKbId = e.dataTransfer.getData('sourceKbId');
    
    if (docId && sourceKbId && onDocumentDrop) {
      onDocumentDrop(docId, sourceKbId, targetKbId);
    }
  };

  return (
    <div className={styles.sidebar}>
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>我的知识库</h3>
          <button className={styles.addBtn} onClick={onCreateClick} title="新建知识库">
            <Plus size={16} />
          </button>
        </div>

        <div className={styles.list}>
          {knowledgeBases.length === 0 ? (
            <div className={styles.empty}>
              <Database size={24} className={styles.emptyIcon} />
              <p className={styles.emptyText}>还没有知识库</p>
              <button className={styles.emptyBtn} onClick={onCreateClick}>
                创建第一个
              </button>
            </div>
          ) : (
            knowledgeBases.map((kb) => (
              <div
                key={kb.id}
                className={`${styles.item} ${isActive(kb.id) ? styles.active : ''} ${dragOverKbId === kb.id ? styles.dragOver : ''}`}
                onClick={() => handleKBClick(kb.id)}
                onDragOver={(e) => handleDragOver(e, kb.id)}
                onDragLeave={handleDragLeave}
                onDrop={(e) => handleDrop(e, kb.id)}
              >
                <img src={getKnowledgeBaseAvatar(kb)} alt={kb.name} className={styles.avatar} />
                <div className={styles.itemBody}>
                  <div className={styles.itemName}>{kb.name}</div>
                  <div className={styles.itemMeta}>{kb.contents || 0} 文档</div>
                </div>
                <button
                  className={styles.menuBtn}
                  onClick={(e) => handleMenuClick(e, kb.id)}
                >
                  <MoreVertical size={14} />
                </button>

                {menuOpen === kb.id && (
                  <div className={styles.menu}>
                    <button className={styles.menuItem} onClick={(e) => handleEdit(e, kb)}>
                      <Edit2 size={14} />
                      <span>编辑</span>
                    </button>
                    <button
                      className={`${styles.menuItem} ${styles.danger}`}
                      onClick={(e) => handleDelete(e, kb.id)}
                    >
                      <Trash2 size={14} />
                      <span>删除</span>
                    </button>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h3 className={styles.sectionTitle}>订阅的知识库</h3>
        </div>

        <div className={styles.list}>
          {subscriptions.length === 0 ? (
            <div className={styles.empty}>
              <Database size={24} className={styles.emptyIcon} />
              <p className={styles.emptyText}>还没有订阅知识库</p>
              <button className={styles.emptyBtn} onClick={() => navigate('/knowledge')}>
                去论文广场看看
              </button>
            </div>
          ) : (
            subscriptions.map((kb) => (
              <div
                key={kb.id}
                className={`${styles.item} ${isActive(kb.id) ? styles.active : ''}`}
                onClick={() => handleKBClick(kb.id)}
              >
                <img src={getKnowledgeBaseAvatar(kb)} alt={kb.name} className={styles.avatar} />
                <div className={styles.itemBody}>
                  <div className={styles.itemName}>{kb.name}</div>
                  <div className={styles.itemMeta}>{kb.contents || 0} 文档</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
});

KnowledgeSidebar.displayName = 'KnowledgeSidebar';

export default KnowledgeSidebar;

