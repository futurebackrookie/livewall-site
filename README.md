# 官网

自包含的静态站点，五种语言。没有构建工具链、没有 npm、没有外部依赖 ——
生成出来的 HTML 丢到任何静态托管上就能跑。

## 文件

| 文件 | 说明 |
|---|---|
| `template.html` | **唯一的结构源文件**，文案位置是 `{{键名}}` 占位符 |
| `locales/*.json` | 五种语言的文案。`zh-Hans` 是基准 |
| `build.py` | 生成各语言页面，**不要手改生成结果** |
| `tools/lint_locales.py` | 语言文件体检（词条完整性、HTML 结构、语言串味） |
| `tools/extract.py` | 一次性脚本，当初把中文页拆成模板 + 词条用的 |
| `deploy.sh` | 校验 → 生成 → 同步到公开的 swaylume-site 仓库 |
| `icon.png` / `og-cover.*` | favicon 与社交分享卡片 |

生成结果（都别手改）：`index.html`（中文）、`en/` `ja/` `de/` `fr/`、
`content.html`（中文片段，供预览页用）、`sitemap.xml`、`robots.txt`。

## 改文案

改 `locales/*.json` 里对应的键，然后：

```bash
python3 site/tools/lint_locales.py && python3 site/build.py
```

**改结构**（加分节、调样式）改 `template.html`；新增文案时记得五个语言文件都要加，
`lint_locales.py` 会告诉你漏了哪个。

部署到别的地址时，把站点地址告诉构建脚本，以便生成正确的 canonical / hreflang：

```bash
SWAYLUME_SITE_URL=https://your-domain.com python3 site/build.py
```

## 多语言是怎么做的

**编译期生成静态页，不是 JS 运行时切换。** 做多语言的目的是让非中文用户
*搜得到*；JS 切换的话每种语言没有自己的网址，搜索引擎只收录默认那一版，等于白做。
现在每种语言都是真实 URL，页头互相声明 `hreflang`，导航里的语言切换器用的是
真链接而不是 JS 下拉 —— 爬虫要能顺着它走。

`/` 是中文，其余在 `/en/` `/ja/` `/de/` `/fr/`。**不做自动跳转**：按浏览器语言
强制跳转既伤 SEO 又惹人烦。想换默认语言就改 `build.py` 里的 `DEFAULT`。

页面脚本里的文案（层级读数、调速器日志、精选卡片）由 `build.py` 注入到
`window.__I18N`，脚本用 `T("键名")` 取。**JS 里写死中文的话，切到英文后
交互部分会突然变回中文** —— 这是最容易漏的一处。

### 三条机器化的检查

翻译最容易出的不是措辞问题，而是人眼在 5 种语言 × 182 条里发现不了的东西。
`lint_locales.py` 查这三类：

1. **词条不匹配** —— 少一条，页面上就会冒出一句中文
2. **HTML 结构漂移** —— 某一版少了 `</strong>`，或 `href` 被顺手"翻译"掉
3. **语言串味** —— 日语里混进简体字（`帧率`、`设置`），英德法里混进汉字

### sitemap 与收录

`build.py` 会生成多语言 `sitemap.xml` —— 每条 URL 都列出全部语言版本（含它自己）
和 `x-default`。只列 5 个 `<loc>` 而不带 `xhtml:link` 的话，搜索引擎不知道它们是
同一内容的不同语言，可能当成互相重复的页面。

`lastmod` 取的是 `template.html` 和 `locales/*.json` 的最新修改时间，**不是构建时间** ——
用构建时间的话每次重新生成都会变一遍，等于反复喊「内容更新了」，久了就不被当真。

> ⚠️ **`robots.txt` 在 github.io 子路径下不生效。**
> 爬虫只读域名根部的 `robots.txt`，`/swaylume-site/robots.txt` 会被忽略。
> 文件照样生成，是为了将来绑自定义域名时自动生效。在那之前，让 sitemap 被发现的
> 唯一办法是去 Google Search Console / Bing 站长工具**手动提交一次**：
> `https://futurebackrookie.github.io/swaylume-site/sitemap.xml`

## 部署

### ⚠️ 先看这条

**GitHub Pages 对私有仓库要付费**（需要 Pro）。Swaylume 主仓库是私有的，
所以官网单独放在公开的 `swaylume-site` 仓库里。同步用：

```bash
./site/deploy.sh "改了什么"
```

脚本会先跑校验、再生成、再推送。别手工 copy —— 上次手工同步的结果就是
线上和本地悄悄分叉。

### 自定义域名

不是必需的。`.com` 一年 ¥60–80，等真要推广了再买 —— `github.io` 的地址一样能用。
买了之后记得用 `SWAYLUME_SITE_URL` 重新生成，否则 canonical 和 hreflang 还指着旧地址。

## 页面里有什么

首屏、「精选壁纸」和「图层」各跑一个 WebGL 片元着色器（域扭曲 fbm + 余弦调色板）。
精选区的四张壁纸可点击切换，首屏同步淡入淡出；画布离开视口即停止渲染。

「图层」那块桌面是可交互的：扳开关能看到壁纸在图标层上下切换，读数会跟着显示
真实的窗口层级值（`−2147483604` ↔ `−2147483601`）。

页面自己也遵守它宣传的省电规矩 —— 画布滚出视野、标签页切走、
或者演示里那个窗口铺满时，`requestAnimationFrame` 就停了。
`prefers-reduced-motion` 下只画一帧。

没有分析脚本、追踪像素或第三方运行时依赖。

## 排版上的雷（都踩过）

- **德语比中文长约 12%**，法语相近。加文案后至少在 375px 和 1100px 各看一遍。
- **CSS 断点必须写在基础规则之后**。写在前面的话同权重后写的赢，断点根本不生效 ——
  德语手机端的四列数据格就是这么冲出屏幕的。
- **`padding` 简写会清掉 `padding-inline`**。`.hero-body` 用 `padding: 128px 0 …`
  把 `.wrap` 的左右内边距抹平，手机上整个首屏贴边。要用 `padding-block`。
- **网格里别让 `auto` 列去挤固定内容**。调速器日志用 `1fr auto` 时，德语的长状态标签
  会把时间戳挤到 18px。改成 `max-content minmax(0,1fr)`。

## 需要你填的地方

- 上架后把「Mac App Store」入口补上（现在只有 GitHub Releases）
- 改 `og-cover.svg` 后记得同步导出 1200×630 的 `og-cover.png`，社交平台读的是 PNG
- 首屏是实时演示。等录好真实的 4K 桌面操作视频，可在首屏加「观看实录」按钮，
  但不要用 AI 生成的假 App 截图替代真实录屏
