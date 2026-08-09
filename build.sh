#!/bin/bash
# content.html -> index.html
#
# 内容只写一遍，两处使用：
#   - content.html  片段（不带 <!doctype>/<html>/<head>/<body>），给 Artifact 预览用
#   - index.html    完整文档，给 GitHub Pages / Cloudflare Pages 等自托管用
#
# <title> 和 <meta name="description"> 在片段里写在最前面（Artifact 需要），
# 生成完整文档时把这两行搬进 <head> —— 它们出现在 <body> 里是不合法的。
set -euo pipefail
cd "$(dirname "$0")"

# GitHub Pages 是默认地址；迁到 Cloudflare 或自定义域名时只需在构建前设一次：
# LIVEWALL_SITE_URL=https://livewall.example.com ./build.sh
site_url="${LIVEWALL_SITE_URL:-https://futurebackrookie.github.io/livewall-site}"
site_url="${site_url%/}"

head_lines=$(grep -E '^<(title|meta name="description")' content.html)
body=$(grep -vE '^<(title|meta name="description")' content.html)

{
  echo '<!doctype html>'
  echo '<html lang="zh-Hans">'
  echo '<head>'
  echo '<meta charset="utf-8">'
  echo '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
  echo "$head_lines"
  echo '<meta name="theme-color" content="#08070E" media="(prefers-color-scheme: dark)">'
  echo '<meta name="theme-color" content="#F2F1F7" media="(prefers-color-scheme: light)">'
  echo "<link rel=\"canonical\" href=\"${site_url}/\">"
  echo '<meta property="og:title" content="LiveWall — macOS 动态壁纸">'
  echo '<meta property="og:description" content="让视频、WebGL 和分层壁纸真正跑在你的 Mac 桌面图标之下。">'
  echo '<meta property="og:type" content="website">'
  echo '<meta property="og:locale" content="zh_CN">'
  echo "<meta property=\"og:url\" content=\"${site_url}/\">"
  echo "<meta property=\"og:image\" content=\"${site_url}/og-cover.png\">"
  echo '<meta property="og:image:width" content="1200">'
  echo '<meta property="og:image:height" content="630">'
  echo '<meta name="twitter:card" content="summary_large_image">'
  echo '<meta name="twitter:title" content="LiveWall — macOS 动态壁纸">'
  echo '<meta name="twitter:description" content="为 Mac 从头写的动态壁纸应用。">'
  echo "<meta name=\"twitter:image\" content=\"${site_url}/og-cover.png\">"
  echo '<link rel="icon" type="image/png" href="icon.png">'
  echo '<link rel="apple-touch-icon" href="icon.png">'
  echo '<script type="application/ld+json">'
  # downloadUrl 必须指向公开仓库。源码仓库 LiveWall 是私有的，
  # 对未登录访客一律 404 —— 写进结构化数据等于告诉搜索引擎一个死链，
  # 也不能写 codeRepository（源码根本不对外）。
  echo '{"@context":"https://schema.org","@type":"SoftwareApplication","name":"LiveWall","applicationCategory":"UtilitiesApplication","operatingSystem":"macOS 14 or later","description":"Native macOS live wallpaper app for video, WebGL and layered wallpapers.","softwareVersion":"Beta","downloadUrl":"https://github.com/futurebackrookie/livewall-site/releases","offers":{"@type":"Offer","price":"0","priceCurrency":"USD"}}'
  echo '</script>'
  echo '</head>'
  echo '<body>'
  echo "$body"
  echo '</body>'
  echo '</html>'
} > index.html

echo "index.html 已生成（$(wc -c < index.html | tr -d ' ') 字节）"
