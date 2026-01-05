import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Users, Calendar, Copy, RefreshCw, Trash2, Settings as SettingsIcon } from 'lucide-react';
import styles from './OrganizationDetail.module.css';
import { organizationAPI } from '@/lib/api';
import { useToast } from '@/hooks/useToast';

interface Organization {
  id: string;
  name: string;
  description?: string;
  avatar?: string;
  org_code: string;
  owner_id: string;
  member_count: number;
  created_at: string;
  code_expires_at?: string | null;
}

interface Member {
  id: string;
  user_id: string;
  user_name: string;
  user_avatar?: string;
  role: string;
  joined_at: string;
}

export default function OrganizationDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const toast = useToast();
  
  const [org, setOrg] = useState<Organization | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentUserId, setCurrentUserId] = useState<string>('');

  useEffect(() => {
    if (id) {
      loadData();
    }
  }, [id]);

  const loadData = async () => {
    if (!id) return;
    
    try {
      setLoading(true);
      const [orgData, membersData] = await Promise.all([
        organizationAPI.get(id),
        organizationAPI.getMembers(id),
      ]);
      
      setOrg(orgData);
      setMembers(membersData.members || []);
      
      // 获取当前用户ID（从localStorage或API）
      const authUser = localStorage.getItem('auth_user');
      if (authUser) {
        const user = JSON.parse(authUser);
        setCurrentUserId(user.id);
      }
    } catch (error: any) {
      toast.error(error.message || '加载失败');
      navigate('/organizations');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyCode = async () => {
    if (!org) return;
    try {
      await navigator.clipboard.writeText(org.org_code);
      toast.success('组织码已复制');
    } catch (error) {
      toast.error('复制失败');
    }
  };

  const handleRegenerateCode = async () => {
    if (!org || !id) return;
    if (!confirm('重新生成组织码后，旧的组织码将立即失效。确定继续吗？')) return;
    
    try {
      const result = await organizationAPI.regenerateCode(id);
      setOrg({ ...org, org_code: result.org_code });
      toast.success('组织码已更新');
    } catch (error: any) {
      toast.error(error.message || '操作失败');
    }
  };

  const handleRemoveMember = async (memberId: string, userName: string) => {
    if (!id) return;
    if (!confirm(`确定要移除成员 "${userName}" 吗？`)) return;
    
    try {
      await organizationAPI.removeMember(id, memberId);
      toast.success('成员已移除');
      loadData();
    } catch (error: any) {
      toast.error(error.message || '移除失败');
    }
  };

  const handleDeleteOrg = async () => {
    if (!id) return;
    if (!confirm('确定要解散该组织吗？此操作不可恢复！')) return;
    
    try {
      await organizationAPI.delete(id);
      toast.success('组织已解散');
      navigate('/organizations');
    } catch (error: any) {
      toast.error(error.message || '解散失败');
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' });
  };

  const getInitials = (name: string) => {
    return name.substring(0, 2).toUpperCase();
  };

  if (loading) {
    return <div className={styles.container}>加载中...</div>;
  }

  if (!org) {
    return <div className={styles.container}>组织不存在</div>;
  }

  const isOwner = org.owner_id === currentUserId;

  return (
    <div className={styles.container}>
      <button className={styles.backBtn} onClick={() => navigate('/organizations')}>
        <ArrowLeft size={16} />
        返回组织列表
      </button>

      <div className={styles.header}>
        <div className={styles.orgAvatar}>
          {org.avatar ? (
            <img src={org.avatar} alt={org.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            getInitials(org.name)
          )}
        </div>
        <div className={styles.headerInfo}>
          <h1 className={styles.orgName}>{org.name}</h1>
          <div className={styles.orgMeta}>
            <div className={styles.metaItem}>
              <Users size={14} />
              <span>{org.member_count} 成员</span>
            </div>
            <div className={styles.metaItem}>
              <Calendar size={14} />
              <span>创建于 {formatDate(org.created_at)}</span>
            </div>
          </div>
          {org.description && (
            <p className={styles.orgDescription}>{org.description}</p>
          )}
          {isOwner && (
            <div className={styles.orgCodeSection}>
              <span className={styles.codeLabel}>组织码：</span>
              <span className={styles.codeValue}>{org.org_code}</span>
              <button className={styles.copyBtn} onClick={handleCopyCode}>
                <Copy size={12} />
                复制
              </button>
            </div>
          )}
        </div>
      </div>

      <div className={styles.content}>
        {/* Members List */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <h2 className={styles.cardTitle}>
              <Users size={18} />
              组织成员
            </h2>
          </div>
          <div className={styles.memberList}>
            {members.map((member) => (
              <div key={member.id} className={styles.memberItem}>
                <div className={styles.memberAvatar}>
                  {member.user_avatar ? (
                    <img src={member.user_avatar} alt={member.user_name} style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '8px' }} />
                  ) : (
                    getInitials(member.user_name)
                  )}
                </div>
                <div className={styles.memberInfo}>
                  <div className={styles.memberName}>{member.user_name}</div>
                  <div className={styles.memberRole}>
                    {member.role === 'owner' ? '创建者' : '成员'} · 加入于 {formatDate(member.joined_at)}
                  </div>
                </div>
                {isOwner && member.role !== 'owner' && (
                  <button 
                    className={styles.removeBtn}
                    onClick={() => handleRemoveMember(member.user_id, member.user_name)}
                  >
                    移除
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Settings (Owner only) */}
        {isOwner && (
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <h2 className={styles.cardTitle}>
                <SettingsIcon size={18} />
                组织设置
              </h2>
            </div>
            <div className={styles.settingsList}>
              <div className={styles.settingItem}>
                <div>
                  <div className={styles.settingLabel}>重新生成组织码</div>
                  <div className={styles.settingDesc}>旧的组织码将立即失效</div>
                </div>
                <button 
                  className={`${styles.actionBtn} ${styles.actionSecondary}`}
                  onClick={handleRegenerateCode}
                >
                  <RefreshCw size={14} />
                  重新生成
                </button>
              </div>

              <div className={styles.settingItem}>
                <div>
                  <div className={styles.settingLabel}>解散组织</div>
                  <div className={styles.settingDesc}>此操作不可恢复，所有成员将被移除</div>
                </div>
                <button 
                  className={`${styles.actionBtn} ${styles.actionDanger}`}
                  onClick={handleDeleteOrg}
                >
                  <Trash2 size={14} />
                  解散组织
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

