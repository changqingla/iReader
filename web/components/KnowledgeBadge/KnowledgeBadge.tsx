import React from 'react';
import { Award, Building2 } from 'lucide-react';
import styles from './KnowledgeBadge.module.css';

interface KnowledgeBadgeProps {
  type: 'admin' | 'organization';
  organizationName?: string;
}

export default function KnowledgeBadge({ type, organizationName }: KnowledgeBadgeProps) {
  if (type === 'admin') {
    return (
      <span className={`${styles.badge} ${styles.adminBadge}`}>
        <Award size={12} className={styles.icon} />
        管理员推荐
      </span>
    );
  }

  return (
    <span className={`${styles.badge} ${styles.orgBadge}`}>
      <Building2 size={12} className={styles.icon} />
      来自 {organizationName || '组织'}
    </span>
  );
}

