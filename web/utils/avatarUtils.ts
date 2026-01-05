/**
 * 知识库头像工具函数
 * 根据知识库分类自动选择对应的头像
 */

// 分类到头像文件的映射
const CATEGORY_AVATAR_MAP: { [key: string]: string } = {
  "哲学": "/paper/zhexue.jpg",
  "经济学": "/paper/jingji.jpg", 
  "法学": "/paper/faxue.jpg",
  "教育学": "/paper/jiaoyu.jpg",
  "文学": "/paper/wenxue.jpg",
  "历史学": "/paper/lishi.jpg",
  "理学": "/paper/lixue.jpg",
  "工学": "/paper/gongxue.jpg",
  "农学": "/paper/nongxue.jpg",
  "医学": "/paper/yixue.jpg",
  "管理学": "/paper/guanli.jpg",
  "艺术学": "/paper/yishu.jpg",
  "其它": "/paper/qita.jpg"
};

/**
 * 根据知识库分类获取对应的头像URL
 * @param category 知识库分类
 * @returns 头像URL路径
 */
export function getCategoryAvatar(category: string): string {
  return CATEGORY_AVATAR_MAP[category] || CATEGORY_AVATAR_MAP["其它"];
}

/**
 * 获取知识库的显示头像
 * 优先使用自定义头像，如果没有则使用分类默认头像
 * @param kb 知识库对象
 * @returns 头像URL路径
 */
export function getKnowledgeBaseAvatar(kb: { avatar?: string; category?: string }): string {
  // 如果有自定义头像且不是默认的kb.png，则使用自定义头像
  if (kb.avatar && kb.avatar !== '/kb.png' && !kb.avatar.includes('/kb.png')) {
    return kb.avatar;
  }
  
  // 否则根据分类返回对应头像
  return getCategoryAvatar(kb.category || '其它');
}
