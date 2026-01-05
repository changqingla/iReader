import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import 'katex/dist/katex.min.css'; // KaTeX样式
import '../styles/markdown.css';

interface OptimizedMarkdownProps {
  children: string;
  className?: string;
}

/**
 * 紧凑型Markdown渲染组件
 * 
 * 设计理念：
 * 1. 不做任何内容预处理，保持Markdown语法完整性
 * 2. 通过自定义组件强制所有元素 margin:0
 * 3. 用CSS选择器精确控制相邻元素间距
 */
export default function OptimizedMarkdown({ children, className }: OptimizedMarkdownProps) {
  return (
    <div className={`markdown-content ${className || ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex, rehypeRaw]}
        components={{
          // 表格：增加水平滚动容器，防止撑破布局
          table: ({ children, ...props }) => (
            <div className="table-wrapper">
              <table {...props}>{children}</table>
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
