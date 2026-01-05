-- Migration: 创建组织成员表
-- Date: 2025-12-09
-- Description: 管理组织与用户的多对多关系

-- 创建组织成员表
CREATE TABLE IF NOT EXISTS organization_members (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(20) DEFAULT 'member', -- 'owner', 'member'
    joined_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(org_id, user_id) -- 确保同一用户不能重复加入同一组织
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_org_members_org ON organization_members(org_id);
CREATE INDEX IF NOT EXISTS idx_org_members_user ON organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_org_members_role ON organization_members(role);
CREATE INDEX IF NOT EXISTS idx_org_members_joined_at ON organization_members(joined_at);

-- 添加注释
COMMENT ON TABLE organization_members IS '组织成员表';
COMMENT ON COLUMN organization_members.role IS '角色：owner(所有者)/member(成员)';
COMMENT ON COLUMN organization_members.joined_at IS '加入时间';

