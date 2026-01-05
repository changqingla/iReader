import React, { useState, useRef, useEffect } from 'react';
import { X, ChevronDown, Check } from 'lucide-react';
import { KNOWLEDGE_CATEGORIES, CATEGORY_ICONS, CATEGORY_COLORS } from '@/constants/categories';
import { useToast } from '@/hooks/useToast';
import styles from './CreateKnowledgeModal.module.css';

interface CreateKnowledgeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: { name: string; description: string; category: string }) => void;
}

export default function CreateKnowledgeModal({ isOpen, onClose, onSubmit }: CreateKnowledgeModalProps) {
  const toast = useToast();
  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [category, setCategory] = React.useState('其它');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // 关闭下拉菜单的点击外部处理
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

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

    onSubmit({
      name: trimmedName,
      description: trimmedDescription,
      category
    });

    // 重置表单
    setName('');
    setDescription('');
    setCategory('其它');
    setIsDropdownOpen(false);
    onClose();
  };

  const handleClose = () => {
    setName('');
    setDescription('');
    setCategory('其它');
    setIsDropdownOpen(false);
    onClose();
  };

  const handleCategorySelect = (cat: string) => {
    setCategory(cat);
    setIsDropdownOpen(false);
  };

  if (!isOpen) return null;

  const SelectedIcon = CATEGORY_ICONS[category];

  return (
    <div className={styles.overlay} onClick={handleClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>新建知识库</h2>
          <button className={styles.closeBtn} onClick={handleClose}>
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.field}>
            <label className={styles.label}>
              知识库名称 <span className={styles.required}>*</span>
              <span className={styles.hint}>（最多8个汉字或16个字母）</span>
            </label>
            <input
              type="text"
              className={styles.input}
              placeholder="输入知识库名称"
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
              placeholder="简单描述这个知识库的用途和内容"
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
            <label className={styles.label}>
              分类 <span className={styles.required}>*</span>
            </label>
            
            <div className={styles.selectWrapper} ref={dropdownRef}>
              <div 
                className={`${styles.selectTrigger} ${isDropdownOpen ? styles.open : ''}`}
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              >
                <div className={styles.selectedContent}>
                  {SelectedIcon && (
                    <SelectedIcon 
                      size={18} 
                      style={{ color: CATEGORY_COLORS[category] }} 
                      className={styles.categoryIcon}
                    />
                  )}
                  <span>{category}</span>
                </div>
                <ChevronDown 
                  size={16} 
                  className={`${styles.chevron} ${isDropdownOpen ? styles.rotate : ''}`}
                />
              </div>
              
              {isDropdownOpen && (
                <div className={styles.selectDropdown}>
                  {KNOWLEDGE_CATEGORIES.map((cat) => {
                    const Icon = CATEGORY_ICONS[cat];
                    const isSelected = category === cat;
                    return (
                      <div 
                        key={cat} 
                        className={`${styles.selectOption} ${isSelected ? styles.selected : ''}`}
                        onClick={() => handleCategorySelect(cat)}
                      >
                        <div className={styles.optionContent}>
                          {Icon ? (
                            <Icon 
                              size={18} 
                              style={{ color: CATEGORY_COLORS[cat] }} 
                              className={styles.categoryIcon}
                            />
                          ) : (
                            <div className={styles.categoryIconPlaceholder} />
                          )}
                          <span className={styles.optionLabel}>{cat}</span>
                        </div>
                        {isSelected && <Check size={16} className={styles.checkIcon} />}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className={styles.actions}>
            <button type="button" className={styles.cancelBtn} onClick={handleClose}>
              取消
            </button>
            <button type="submit" className={styles.submitBtn}>
              创建
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

