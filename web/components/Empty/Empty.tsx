import React from 'react';
import { LucideIcon } from 'lucide-react';
import styles from './Empty.module.css';

interface EmptyProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
}

export default function Empty({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyProps) {
  return (
    <div className={`${styles.empty} ${className || ''}`}>
      {Icon && (
        <div className={styles.iconWrapper}>
          <Icon size={48} />
        </div>
      )}
      <h3 className={styles.title}>{title}</h3>
      {description && <p className={styles.description}>{description}</p>}
      {action && (
        <button className={styles.actionBtn} onClick={action.onClick}>
          {action.label}
        </button>
      )}
    </div>
  );
}

