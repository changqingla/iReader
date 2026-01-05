/**
 * 组织管理 Hook
 * 提供组织相关的数据和操作方法
 */
import { useState, useEffect, useCallback } from 'react';
import { organizationAPI } from '@/lib/api';
import { useToast } from './useToast';

export interface Organization {
  id: string;
  name: string;
  description: string;
  owner_id: string;
  owner_name: string;
  org_code: string;
  code_expires_at: string | null;
  member_count: number;
  created_at: string;
  role: 'owner' | 'member';
}

export function useOrganizations() {
  const toast = useToast();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 加载组织列表
   */
  const fetchOrganizations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await organizationAPI.list();
      // 合并 created 和 joined 为一个数组
      const allOrgs = [...(data.created || []), ...(data.joined || [])];
      setOrganizations(allOrgs);
    } catch (err: any) {
      const errorMsg = err.message || '加载组织列表失败';
      setError(errorMsg);
      console.error('Failed to fetch organizations:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * 创建组织
   */
  const createOrganization = useCallback(
    async (data: { name: string; description: string }) => {
      try {
        const result = await organizationAPI.create(data);
        toast.success('组织创建成功');
        await fetchOrganizations();
        return result;
      } catch (err: any) {
        const errorMsg = err.message || '创建组织失败';
        toast.error(errorMsg);
        throw err;
      }
    },
    [toast, fetchOrganizations]
  );

  /**
   * 加入组织
   */
  const joinOrganization = useCallback(
    async (orgCode: string) => {
      try {
        await organizationAPI.join(orgCode);
        toast.success('成功加入组织');
        await fetchOrganizations();
      } catch (err: any) {
        const errorMsg = err.message || '加入组织失败';
        toast.error(errorMsg);
        throw err;
      }
    },
    [toast, fetchOrganizations]
  );

  /**
   * 退出组织
   */
  const leaveOrganization = useCallback(
    async (orgId: string) => {
      try {
        await organizationAPI.leave(orgId);
        toast.success('已退出组织');
        await fetchOrganizations();
      } catch (err: any) {
        const errorMsg = err.message || '退出组织失败';
        toast.error(errorMsg);
        throw err;
      }
    },
    [toast, fetchOrganizations]
  );

  /**
   * 解散组织
   */
  const deleteOrganization = useCallback(
    async (orgId: string) => {
      try {
        await organizationAPI.delete(orgId);
        toast.success('组织已解散');
        await fetchOrganizations();
      } catch (err: any) {
        const errorMsg = err.message || '解散组织失败';
        toast.error(errorMsg);
        throw err;
      }
    },
    [toast, fetchOrganizations]
  );

  /**
   * 更新组织信息
   */
  const updateOrganization = useCallback(
    async (orgId: string, data: { name?: string; description?: string }) => {
      try {
        await organizationAPI.update(orgId, data);
        toast.success('组织信息已更新');
        await fetchOrganizations();
      } catch (err: any) {
        const errorMsg = err.message || '更新组织信息失败';
        toast.error(errorMsg);
        throw err;
      }
    },
    [toast, fetchOrganizations]
  );

  /**
   * 重新生成组织码
   */
  const regenerateOrgCode = useCallback(
    async (orgId: string) => {
      try {
        const result = await organizationAPI.regenerateCode(orgId);
        toast.success('组织码已重新生成');
        await fetchOrganizations();
        return result.org_code;
      } catch (err: any) {
        const errorMsg = err.message || '重新生成组织码失败';
        toast.error(errorMsg);
        throw err;
      }
    },
    [toast, fetchOrganizations]
  );

  /**
   * 设置组织码有效期
   */
  const setCodeExpiry = useCallback(
    async (orgId: string, expiresAt: string | null) => {
      try {
        await organizationAPI.setCodeExpiry(orgId, expiresAt);
        toast.success('组织码有效期已设置');
        await fetchOrganizations();
      } catch (err: any) {
        const errorMsg = err.message || '设置组织码有效期失败';
        toast.error(errorMsg);
        throw err;
      }
    },
    [toast, fetchOrganizations]
  );

  // 初次加载
  useEffect(() => {
    fetchOrganizations();
  }, [fetchOrganizations]);

  // 获取拥有的组织
  const ownedOrganizations = organizations.filter((org) => org.role === 'owner');
  
  // 获取加入的组织
  const joinedOrganizations = organizations.filter((org) => org.role === 'member');

  return {
    organizations,
    ownedOrganizations,
    joinedOrganizations,
    loading,
    error,
    fetchOrganizations,
    createOrganization,
    joinOrganization,
    leaveOrganization,
    deleteOrganization,
    updateOrganization,
    regenerateOrgCode,
    setCodeExpiry,
  };
}

