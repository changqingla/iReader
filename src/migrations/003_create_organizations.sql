-- Migration: 创建组织表
-- Date: 2025-12-09
-- Description: 用于管理用户组织，支持组织码加入和成员管理

-- 创建组织表
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    avatar VARCHAR(255),
    org_code VARCHAR(20) UNIQUE NOT NULL,
    code_expires_at TIMESTAMP NULL, -- 组织码有效期
    owner_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    max_members INTEGER DEFAULT 50, -- 根据创建者等级自动设置
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE -- 软删除标记
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_organizations_owner ON organizations(owner_id);
CREATE INDEX IF NOT EXISTS idx_organizations_code ON organizations(org_code);
CREATE INDEX IF NOT EXISTS idx_organizations_deleted ON organizations(is_deleted);
CREATE INDEX IF NOT EXISTS idx_organizations_name ON organizations(name);
CREATE INDEX IF NOT EXISTS idx_organizations_created_at ON organizations(created_at);

-- 添加注释
COMMENT ON TABLE organizations IS '组织表';
COMMENT ON COLUMN organizations.name IS '组织名称';
COMMENT ON COLUMN organizations.org_code IS '组织码，用于其他用户加入';
COMMENT ON COLUMN organizations.code_expires_at IS '组织码有效期，过期后无法加入';
COMMENT ON COLUMN organizations.max_members IS '最大成员数，根据创建者等级确定';
COMMENT ON COLUMN organizations.is_deleted IS '是否已解散（软删除）';

