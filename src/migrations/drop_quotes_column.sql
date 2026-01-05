-- 数据库迁移脚本：删除 chat_messages.quotes 列
-- 创建时间: 2025-11-14
-- 目的: 移除未使用的 quotes 功能

-- 步骤1: 备份现有数据（可选，但强烈建议）
CREATE TABLE IF NOT EXISTS chat_messages_backup_20251114 AS 
SELECT * FROM chat_messages;

-- 步骤2: 删除 quotes 列的索引（如果存在）
DROP INDEX IF EXISTS idx_chat_messages_quotes;

-- 步骤3: 删除 quotes 列
ALTER TABLE chat_messages 
DROP COLUMN IF EXISTS quotes;

-- 步骤4: 验证迁移结果
-- 检查列是否已删除
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'chat_messages';

-- 步骤5: （可选）删除备份表
-- 只有在确认迁移成功后才执行
-- DROP TABLE IF EXISTS chat_messages_backup_20251114;

-- 注意事项:
-- 1. 在生产环境执行前，请先在测试环境验证
-- 2. 建议在低峰期执行迁移
-- 3. 迁移期间会锁定表，可能影响应用可用性
-- 4. 确保应用代码已经移除了所有 quotes 相关的引用

