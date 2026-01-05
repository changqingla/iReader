-- Migration: 创建激活码表
-- Date: 2025-12-09
-- Description: 用于管理会员激活码的生成、使用和作废

-- 确保 uuid-ossp 扩展已启用
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 创建激活码表
CREATE TABLE IF NOT EXISTS activation_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    type VARCHAR(20) NOT NULL, -- 'member', 'premium'
    duration_days INTEGER NULL, -- NULL 表示永久有效
    max_usage INTEGER DEFAULT 1, -- 最大使用次数
    used_count INTEGER DEFAULT 0, -- 已使用次数
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NULL, -- 激活码本身的有效期
    is_active BOOLEAN DEFAULT TRUE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_activation_codes_code ON activation_codes(code);
CREATE INDEX IF NOT EXISTS idx_activation_codes_type ON activation_codes(type);
CREATE INDEX IF NOT EXISTS idx_activation_codes_active ON activation_codes(is_active);
CREATE INDEX IF NOT EXISTS idx_activation_codes_created_by ON activation_codes(created_by);
CREATE INDEX IF NOT EXISTS idx_activation_codes_expires_at ON activation_codes(expires_at);

-- 添加注释
COMMENT ON TABLE activation_codes IS '激活码表，用于会员激活';
COMMENT ON COLUMN activation_codes.code IS '激活码，唯一标识';
COMMENT ON COLUMN activation_codes.type IS '激活类型：member(会员)/premium(高级会员)';
COMMENT ON COLUMN activation_codes.duration_days IS '激活后会员时长（天），NULL表示永久';
COMMENT ON COLUMN activation_codes.max_usage IS '最大使用次数';
COMMENT ON COLUMN activation_codes.used_count IS '已使用次数';
COMMENT ON COLUMN activation_codes.expires_at IS '激活码有效期，过期后无法使用';
COMMENT ON COLUMN activation_codes.is_active IS '是否有效，管理员可作废';

