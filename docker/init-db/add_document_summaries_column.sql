-- 添加 document_summaries 列到 chat_messages 表
-- 用于存储多文档任务的文档总结信息，便于历史消息恢复

-- 检查列是否存在，如果不存在则添加
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'chat_messages' 
        AND column_name = 'document_summaries'
    ) THEN
        ALTER TABLE chat_messages 
        ADD COLUMN document_summaries JSONB;
        
        COMMENT ON COLUMN chat_messages.document_summaries IS '文档总结信息，格式: [{"doc_id": "xxx", "doc_name": "xxx.pdf", "summary": "...", "from_cache": true}, ...]';
    END IF;
END $$;
