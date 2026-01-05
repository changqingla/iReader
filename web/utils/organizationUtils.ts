/**
 * 组织相关工具函数
 */

export interface UserProfile {
  is_member: boolean;
  is_advanced_member: boolean;
  is_admin: boolean;
  organizations?: Array<{ id: string }>;
}

/**
 * 生成组织头像（基于组织名称的首字母）
 */
export function getOrganizationAvatar(name: string): string {
  if (!name) return '?';
  
  // 获取第一个字符
  const firstChar = name.trim()[0];
  
  // 如果是中文，直接返回
  if (/[\u4e00-\u9fa5]/.test(firstChar)) {
    return firstChar;
  }
  
  // 如果是英文，返回大写
  return firstChar.toUpperCase();
}

/**
 * 格式化组织码（添加分隔符）
 */
export function formatOrganizationCode(code: string): string {
  if (!code) return '';
  
  // 每4位添加一个空格
  return code.toUpperCase().replace(/(.{4})/g, '$1 ').trim();
}

/**
 * 判断用户是否可以创建组织
 */
export function canCreateOrganization(user: UserProfile): {
  canCreate: boolean;
  reason?: string;
} {
  if (user.is_admin) {
    return { canCreate: true };
  }
  
  if (!user.is_member && !user.is_advanced_member) {
    return {
      canCreate: false,
      reason: '普通用户无法创建组织，请先升级为会员',
    };
  }
  
  // 检查是否已经创建了组织
  const ownedOrgsCount = user.organizations?.filter(
    (org: any) => org.role === 'owner'
  ).length || 0;
  
  if (user.is_advanced_member && ownedOrgsCount >= 2) {
    return {
      canCreate: false,
      reason: '您已达到创建组织的上限（2个）',
    };
  }
  
  if (user.is_member && ownedOrgsCount >= 1) {
    return {
      canCreate: false,
      reason: '您已达到创建组织的上限（1个）',
    };
  }
  
  return { canCreate: true };
}

/**
 * 判断用户是否可以加入更多组织
 */
export function canJoinMoreOrganizations(user: UserProfile): {
  canJoin: boolean;
  reason?: string;
  limit: number;
  current: number;
} {
  const joinedOrgsCount = user.organizations?.filter(
    (org: any) => org.role === 'member'
  ).length || 0;
  
  let limit = 1; // 普通用户默认1个
  
  if (user.is_admin) {
    return {
      canJoin: true,
      limit: Infinity,
      current: joinedOrgsCount,
    };
  }
  
  if (user.is_advanced_member) {
    limit = 10;
  } else if (user.is_member) {
    limit = 3;
  }
  
  if (joinedOrgsCount >= limit) {
    return {
      canJoin: false,
      reason: `您已达到加入组织的上限（${limit}个）`,
      limit,
      current: joinedOrgsCount,
    };
  }
  
  return {
    canJoin: true,
    limit,
    current: joinedOrgsCount,
  };
}

/**
 * 获取组织成员上限
 */
export function getOrganizationMemberLimit(ownerLevel: {
  is_member: boolean;
  is_advanced_member: boolean;
  is_admin: boolean;
}): number {
  if (ownerLevel.is_admin) {
    return Infinity;
  }
  
  if (ownerLevel.is_advanced_member) {
    return 500;
  }
  
  if (ownerLevel.is_member) {
    return 100;
  }
  
  return 50; // 普通用户（理论上不应该有组织）
}

/**
 * 计算组织码剩余有效期（天数）
 */
export function getCodeExpiryDays(expiresAt: string | null): number | null {
  if (!expiresAt) return null;
  
  const expiry = new Date(expiresAt);
  const now = new Date();
  const diffMs = expiry.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  
  return diffDays > 0 ? diffDays : 0;
}

/**
 * 格式化组织码有效期显示
 */
export function formatCodeExpiry(expiresAt: string | null): string {
  if (!expiresAt) return '永久有效';
  
  const days = getCodeExpiryDays(expiresAt);
  
  if (days === null || days < 0) return '已过期';
  if (days === 0) return '今天到期';
  if (days === 1) return '明天到期';
  
  return `${days}天后到期`;
}

