/**
 * 编辑知识库模态框组件
 */
import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { KNOWLEDGE_CATEGORIES, CATEGORY_ICONS } from '@/constants/categories';
import { useToast } from '@/hooks/useToast';
import styles from './EditKnowledgeModal.module.css';

interface EditKnowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: { name: string; description: string; category: string }) => void;
  initialData: { name: string; description: string; category: string };
}

export default function EditKnowledgeModal({
  isOpen,
  onClose,
  onSave,
  initialData
}: EditKnowledgeModalProps) {
  const toast = useToast();
  const [name, setName] = React.useState(initialData.name);
  const [description, setDescription] = React.useState(initialData.description);
  const [category, setCategory] = React.useState(initialData.category || '其它');

  useEffect(() => {
    if (isOpen) {
      setName(initialData.name);
      setDescription(initialData.description);
      setCategory(initialData.category || '其它');
    }
  }, [isOpen, initialData]);

  if (!isOpen) return null;

  // 计算字符串长度（中文算2个字符，英文算1个字符）
  const getStringLength = (str: string): number => {
    let length = 0;
    for (let i = 0; i < str.length; i++) {
      const charCode = str.charCodeAt(i);
      // 中文字符范围
      if (charCode >= 0x4e00 && charCode <= 0x9fff) {
        length += 2;
      } else {
        length += 1;
      }
    }
    return length;
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    const length = getStringLength(value);
    
    // 限制最多16个字符（相当于8个汉字或16个英文字母）
    if (length <= 16) {
      setName(value);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!name.trim()) {
      toast.warning('请输入知识库名称');
      return;
    }

    const trimmedName = name.trim();
    const nameLength = getStringLength(trimmedName);
    
    if (nameLength > 16) {
      toast.warning('知识库名称过长，最多8个汉字或16个字母');
      return;
    }

    const trimmedDescription = description.trim();
    const descLength = getStringLength(trimmedDescription);
    if (descLength > 60) {
      toast.warning('知识库描述过长，最多30个汉字或60个字母');
      return;
    }

    onSave({
      name: trimmedName,
      description: trimmedDescription,
      category
    });
    onClose();
  };

  const handleClose = () => {
    onClose();
  };

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>编辑知识库</h2>
          <button className={styles.closeBtn} onClick={handleClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label className={styles.label}>
              知识库名称
              <span className={styles.hint}>（最多8个汉字或16个字母）</span>
            </label>
            <input
              type="text"
              className={styles.input}
              value={name}
              onChange={handleNameChange}
              autoFocus
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label}>
              概述
              <span className={styles.hint}>（最多30个汉字或60个字母）</span>
            </label>
            <textarea
              className={styles.textarea}
              value={description}
              onChange={(e) => {
                const value = e.target.value;
                const length = getStringLength(value);
                if (length <= 60) {
                  setDescription(value);
                }
              }}
              rows={3}
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label}>分类</label>
            <select
              className={styles.select}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {KNOWLEDGE_CATEGORIES.map((cat) => {
                const Icon = CATEGORY_ICONS[cat];
                return (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                );
              })}
            </select>
          </div>

          <div className={styles.actions}>
            <button type="button" className={styles.cancelBtn} onClick={handleClose}>
              取消
            </button>
            <button type="submit" className={styles.saveBtn}>
              保存
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}


