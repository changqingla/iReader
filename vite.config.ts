import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from "vite-tsconfig-paths";
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd() + '/web', '');
  
  // 从环境变量读取配置，提供默认值
  const devPort = parseInt(env.VITE_DEV_PORT || '3003', 10);
  const apiProxyTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:13000';
  const minioProxyTarget = env.VITE_MINIO_PROXY_TARGET || 'http://localhost:9000';

  return {
    css: {
      postcss: {
        plugins: [
          tailwindcss,
          autoprefixer,
        ],
      },
    },
    server: {
      host: '0.0.0.0',
      port: devPort,
      proxy: {
        // 开发环境代理 API 请求到后端
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        // 开发环境代理 MinIO 请求
        '/minio': {
          target: minioProxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/minio/, ''),
        },
      },
    },
    build: {
      sourcemap: 'hidden',
    },
    plugins: [
      react({
        babel: {
          plugins: [
            'react-dev-locator',
          ],
        },
      }),
      tsconfigPaths()
    ],
  }
})
