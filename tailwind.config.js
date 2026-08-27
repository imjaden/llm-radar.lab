/**
 * Tailwind CSS 预编译配置 (llm-radar-CL002 D1/A1)
 * 提取自 index.html 内联 config: colors.cobalt 400/500 + accent 400/500。
 * 产物 static/tailwind.css 入库; 新增 Tailwind 类后必须重跑构建并提交产物 (AGENTS.md O-2)。
 */
module.exports = {
  content: ['index.html', 'changelog.html'],
  theme: {
    extend: {
      colors: {
        cobalt: { 400: '#818cf8', 500: '#6366f1' },
        accent: { 400: '#facc15', 500: '#eab308' },
      }
    }
  },
  plugins: [],
}
