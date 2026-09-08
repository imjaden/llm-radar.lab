# GitHub Emoji 编程与评审约定速查

> Version: 1.0 (2026-07-11)

---

## 一、GitHub Issue / PR / Comment 反应表情（官方内置）

GitHub 在 Issue、PR、Comment 上提供了 6 个内置 reaction 按钮：

| Emoji | Code | 含义 |
|:-----:|:-----|:-----|
| 👍 | `:+1:` | 赞同 / 我也遇到 / +1 |
| 👎 | `:-1:` | 反对 / 不赞同 |
| 😄 | `:smile:` | 开心 / 有趣 / 哈哈 |
| 🎉 | `:tada:` | 庆祝 / 恭喜 / 太好了 |
| 😕 | `:confused:` | 困惑 / 不确定 |
| ❤️ | `:heart:` | 喜欢 / 感谢 / 爱心 |

社区实践中常用的额外 emoji（通过 comment 表情贴）：

| Emoji | Code | 含义 |
|:-----:|:-----|:-----|
| 🚀 | `:rocket:` | 太棒了 / 起飞 / ship it |
| 👀 | `:eyes:` | 我在关注 / 看到了 / 盯着呢 |
| 🙏 | `:pray:` | 感谢 / 拜托了 |
| 💯 | `:100:` | 完美 / 满分 |
| 🤔 | `:thinking:` | 让我想想 / 有点问题 |
| 🙌 | `:raised_hands:` | 干得漂亮 |
| 🔥 | `:fire:` | 热门 / 厉害 |

---

## 二、Git Commit Message Emoji（Gitmoji 标准）

### 编程类

| Emoji | Code | 用途 |
|:-----:|:-----|:-----|
| ✨ | `:sparkles:` | 新功能 / feature |
| 🐛 | `:bug:` | 修 bug / bugfix |
| 🔨 | `:hammer:` | 重构代码 / refactor |
| 🎨 | `:art:` | 改进代码结构/格式 |
| ⚡ | `:zap:` | 性能优化 / perf |
| 🔥 | `:fire:` | 删除代码或文件 |
| 🚑 | `:ambulance:` | 紧急热修复 / critical hotfix |
| 💥 | `:boom:` | 破坏性变更 / breaking change |
| ♻️ | `:recycle:` | 重构 |
| ✏️ | `:pencil2:` | 修 typo |
| 💩 | `:hankey:` | 烂代码需要改进 |
| 🩹 | `:adhesive_bandage:` | 简单修补 / 非关键修复 |
| 🧹 | `:broom:` | 清理死代码 / cleanup |

### 评审类

| Emoji | Code | 用途 |
|:-----:|:-----|:-----|
| 👌 | `:ok_hand:` | 代码评审后修改 / code review changes |
| ✅ | `:white_check_mark:` | 通过测试 / 评审通过 |
| 🚨 | `:rotating_light:` | 添加/修复测试 |
| 💚 | `:green_heart:` | 修复 CI 构建 |
| 🔒 | `:lock:` | 修复安全问题 / security |
| 📝 | `:memo:` | 添加文档或注释 |
| 💡 | `:bulb:` | 添加源码注释 |

### Issue / PR 类

| Emoji | Code | 用途 |
|:-----:|:-----|:-----|
| 🎉 | `:tada:` | 项目初始化 / initial commit |
| 🚀 | `:rocket:` | 部署 / deploy |
| 🔖 | `:bookmark:` | 版本发布 / release tag |
| 🚧 | `:construction:` | WIP 进行中 |
| 👷 | `:construction_worker:` | CI 相关 |
| 🔧 | `:wrench:` | 配置文件修改 |
| 🔀 | `:twisted_rightwards_arrows:` | 合并分支 / merge |
| ⏪ | `:rewind:` | 回滚 / revert |

### 依赖管理类

| Emoji | Code | 用途 |
|:-----:|:-----|:-----|
| ➕ | `:heavy_plus_sign:` | 添加依赖 |
| ➖ | `:heavy_minus_sign:` | 移除依赖 |
| ⬆️ | `:arrow_up:` | 升级依赖 |
| ⬇️ | `:arrow_down:` | 降级依赖 |
| 📌 | `:pushpin:` | 锁定依赖版本 |

### 其他常用

| Emoji | Code | 用途 |
|:-----:|:-----|:-----|
| 📚 | `:books:` | 文档 |
| 🚚 | `:truck:` | 移动/重命名文件 |
| 🍎 | `:apple:` | macOS 相关修复 |
| 🐧 | `:penguin:` | Linux 相关修复 |
| 🏁 | `:checkered_flag:` | Windows 相关修复 |
| 🌐 | `:globe_with_meridians:` | 国际化/本地化 |
| ♿ | `:wheelchair:` | 无障碍 |
| 🗃️ | `:card_file_box:` | 数据库变更 |

---

## 三、社区常用评审 Emoji 速查

| 场景 | Emoji | 含义 |
|:-----|:-----:|:-----|
| 提交 Issue 报告 bug | 🐛 | bug report |
| PR 提交新功能 | ✨ | feature PR |
| PR 请求 review | 👀 | please review |
| PR review 通过 | ✅ / 👍 | approved |
| PR 需要修改 | 🔧 / 🩹 | changes requested |
| MR 合并 | 🔀 | merge |
| 发布版本 | 🔖 / 🚀 | release |
| 代码评审意见 | 👌 | addressed review |
| 点赞/感谢 | ❤️ / 🙏 | thanks |
| 标记讨论 | 🤔 | discussing |

---

## 参考

- [gitmoji.dev](https://gitmoji.dev/) — 官方 gitmoji 参考
- [GitHub Reactions Blog](https://github.blog/news-insights/product-news/add-reactions-to-pull-requests-issues-and-comments/) — GitHub 官方 reaction 公告
- [Gist: Git Commit Message Emoji](https://gist.github.com/parmentf/035de27d6ed1dce0b36a)
