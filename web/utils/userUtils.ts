/**
 * 用户相关工具函数
 */

export interface UserProfile {
  name: string;
  email: string;
  avatar?: string;
  is_member: boolean;
  is_advanced_member: boolean;
  is_admin: boolean;
  member_expires_at?: string;
}

export type UserRole = 'explorer' | 'member' | 'advanced_member' | 'admin';

/**
 * 获取用户身份等级
 */
export function getUserRole(user: UserProfile): UserRole {
  if (user.is_admin) return 'admin';
  if (user.is_advanced_member) return 'advanced_member';
  if (user.is_member) return 'member';
  return 'explorer';
}

/**
 * 获取用户身份等级文本
 */
export function getUserRoleText(user: UserProfile): string {
  const role = getUserRole(user);
  
  switch (role) {
    case 'admin':
      return '管理员';
    case 'advanced_member':
      return '高级会员';
    case 'member':
      return '会员';
    default:
      return '探索者';
  }
}

/**
 * 获取用户身份等级颜色
 */
export function getUserRoleColor(user: UserProfile): {
  bg: string;
  text: string;
  gradient: string;
} {
  const role = getUserRole(user);
  
  switch (role) {
    case 'admin':
      return {
        bg: '#fef2f2',
        text: '#dc2626',
        gradient: 'linear-gradient(135deg, #fca5a5 0%, #f87171 100%)',
      };
    case 'advanced_member':
      return {
        bg: '#faf5ff',
        text: '#9333ea',
        gradient: 'linear-gradient(135deg, #d8b4fe 0%, #c084fc 100%)',
      };
    case 'member':
      return {
        bg: '#eff6ff',
        text: '#2563eb',
        gradient: 'linear-gradient(135deg, #93c5fd 0%, #60a5fa 100%)',
      };
    default:
      return {
        bg: '#f8fafc',
        text: '#64748b',
        gradient: 'linear-gradient(135deg, #cbd5e1 0%, #94a3b8 100%)',
      };
  }
}

/**
 * 计算会员到期天数
 */
export function getMemberExpiryDays(expiresAt?: string): number | null {
  if (!expiresAt) return null;
  
  const expiry = new Date(expiresAt);
  const now = new Date();
  const diffMs = expiry.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
  
  return diffDays > 0 ? diffDays : 0;
}

/**
 * 格式化会员到期时间显示
 */
export function formatMemberExpiry(expiresAt?: string): string {
  if (!expiresAt) return '';
  
  const days = getMemberExpiryDays(expiresAt);
  
  if (days === null || days < 0) return '已过期';
  if (days === 0) return '今天到期';
  if (days <= 7) return `${days}天后到期`;
  if (days <= 30) return `${days}天后到期`;
  
  // 格式化为日期
  const expiry = new Date(expiresAt);
  return `${expiry.getFullYear()}-${String(expiry.getMonth() + 1).padStart(2, '0')}-${String(expiry.getDate()).padStart(2, '0')} 到期`;
}

/**
 * 判断会员是否即将到期（7天内）
 */
export function isMemberExpiringSoon(expiresAt?: string): boolean {
  if (!expiresAt) return false;
  
  const days = getMemberExpiryDays(expiresAt);
  return days !== null && days > 0 && days <= 7;
}

/**
 * 生成用户头像字母（基于用户名）
 */
export function getUserAvatarLetter(name: string): string {
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
 * 验证用户名格式
 */
export function validateUsername(username: string): {
  isValid: boolean;
  error?: string;
} {
  if (!username || username.trim().length === 0) {
    return { isValid: false, error: '用户名不能为空' };
  }
  
  if (username.length < 2) {
    return { isValid: false, error: '用户名至少2个字符' };
  }
  
  if (username.length > 20) {
    return { isValid: false, error: '用户名不能超过20个字符' };
  }
  
  // 只允许中文、英文、数字、下划线
  if (!/^[\u4e00-\u9fa5a-zA-Z0-9_]+$/.test(username)) {
    return {
      isValid: false,
      error: '用户名只能包含中文、英文、数字和下划线',
    };
  }
  
  return { isValid: true };
}

