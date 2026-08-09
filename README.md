# 官网

一个自包含的单页站点。没有构建工具链、没有 npm、没有外部依赖 ——
`index.html` 一个文件丢到任何静态托管上就能跑。

## 文件

| 文件 | 说明 |
|---|---|
| `content.html` | **唯一的源文件**，所有内容和样式都在这 |
| `index.html` | `build.sh` 生成的完整文档，**不要手改** |
| `build.sh` | 给 `content.html` 套上 `<!doctype>` / `<head>` / `<body>` |
| `icon.png` | 从 `Sources/Resources/Assets.xcassets` 缩出来的 favicon |
| `og-cover.svg` / `og-cover.png` | 社交分享卡片源图与已导出的 1200×630 PNG |

改完 `content.html` 跑一下：

```bash
./site/build.sh
```

如果不是部署到 GitHub Pages 默认地址，构建时把实际站点地址告诉脚本，以便生成正确的
canonical、Open Graph、Twitter Card：

```bash
LIVEWALL_SITE_URL=https://your-domain.com ./site/build.sh
```

分成两个文件是因为片段形式（不带 `<!doctype>`）能直接拿去做预览页，
而自托管需要完整文档 —— 内容只写一遍，两边都能用。

## 部署

### ⚠️ 先看这条

**GitHub Pages 对私有仓库要付费**（需要 Pro，$4/月）。LiveWall 主仓库如果是私有的，
Pages 走不通。下面两条路都是**零成本**的：

### 路线 A：单独开一个公开仓库（推荐）

官网本来就是要给人看的，没有保密的必要。

```bash
cd site && git init && git add -A && git commit -m "官网"
gh repo create livewall-site --public --source=. --remote=origin --push
```

然后在仓库的 Settings → Pages 里把源设成 `main` 分支根目录。
地址会是 `https://futurebackrookie.github.io/livewall-site/`。

### 路线 B：Cloudflare Pages

私有仓库也免费，而且绑自定义域名不额外收费。
在 Cloudflare 控制台连上 GitHub 仓库，构建命令留空，输出目录填 `site`。

### 自定义域名

不是必需的。`.com` 域名一年 ¥60–80 左右，等真要推广了再买不迟 ——
`github.io` 的地址一样能用。

## 页面里有什么

首屏、「精选壁纸」和「图层」各跑一个 WebGL 片元着色器（域扭曲 fbm + 余弦调色板）。
精选区的四张壁纸可点击切换，首屏同步淡入淡出；画布离开视口即停止渲染。

「图层」那块桌面是可交互的：扳开关能看到壁纸在图标层上下切换，读数会跟着显示
真实的窗口层级值（`−2147483604` ↔ `−2147483601`）。

页面自己也遵守它宣传的省电规矩 —— 画布滚出视野、标签页切走、
或者演示里那个窗口铺满时，`requestAnimationFrame` 就停了。
`prefers-reduced-motion` 下只画一帧。

页面另有三条用户路径（直接使用 / 从 Windows 导入 / 创作者投稿）、本地优先的隐私说明、
GitHub Releases 下载入口和产品结构化数据。没有分析脚本、追踪像素或第三方运行时依赖。

## 需要你填的地方

- GitHub 链接现在指向 `futurebackrookie/LiveWall`，仓库建好前是 404
- Releases 页面目前是 Beta 构建的唯一正式分发入口；发布第一个资产后无需改网页链接
- 改 `og-cover.svg` 后记得同步导出 1200×630 的 `og-cover.png`，社交平台读取的是 PNG
- 首屏是实时演示。等录好真实的 4K 桌面操作视频，可在首屏背景之上加入「观看 12 秒实录」按钮，
  但不要用 AI 生成的假 App 截图替代真实录屏
