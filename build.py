#!/usr/bin/env python3
"""从 template.html + locales/*.json 生成各语言的站点。

输出：
    content.html        中文片段（不带 <!doctype>，供预览页使用）
    index.html          中文完整文档
    en/index.html       英文
    fr/ ja/ de/         法语 / 日语 / 德语

为什么是编译期生成而不是 JS 运行时切换：做多语言的目的是让非中文用户
**搜得到**。JS 切换的话每种语言没有自己的网址，搜索引擎只会收录默认那一版，
等于白做。编译期出静态页，每种语言都是真实 URL，配 hreflang 互相声明。

用法：./build.py [--check]
      --check  只校验词条完整性，不写文件
"""
import json, re, os, sys, pathlib

SITE_URL = os.environ.get("SWAYLUME_SITE_URL",
                          "https://futurebackrookie.github.io/swaylume-site").rstrip("/")

# 语言代码 -> (输出子目录, <html lang>, og:locale, 语言切换器上的名字)
LOCALES = {
    "zh-Hans": ("",   "zh-Hans", "zh_CN", "简体中文"),
    "en":      ("en", "en",      "en_US", "English"),
    "ja":      ("ja", "ja",      "ja_JP", "日本語"),
    "de":      ("de", "de",      "de_DE", "Deutsch"),
    "fr":      ("fr", "fr",      "fr_FR", "Français"),
}
DEFAULT = "zh-Hans"

# Google Search Console 的所有权验证串。
#
# 这是第二种验证方式 —— 第一种是根目录那个 google*.html 文件。
# 多留一种是因为文件万一被误删就会掉验证状态，而掉了之后 sitemap 的
# 提交记录和「效果」报告都会一并失效。
# 这个串是公开信息，本来就写在页面 <head> 里给 Google 读。
GOOGLE_SITE_VERIFICATION = "93BTzCfdrxJ65LatgdtsEzQOmfIMGR1uFCZ4_jt4318"

# 网页访问统计。留空 = 页面上一个追踪脚本都没有。
#
# 只支持无 cookie 的方案。页面自己有一整节在讲隐私，挂 Google Analytics
# 那种广告产品是自相矛盾 —— 而且欧盟访客还得弹 Cookie 同意条。
#
#   ANALYTICS = ("cloudflare", "你的 token")   # dash.cloudflare.com → Web Analytics
#   ANALYTICS = ("goatcounter", "你的子域名")   # 形如 swaylume（不含 .goatcounter.com）
#
# 这个 token 不是密钥：它会原样出现在每个访客的页面源码里，Cloudflare 就是这么
# 设计的（它标识「统计哪个站点」，不能用来读数据，读数据要登录后台）。
# 所以进版本库没有问题，不用当敏感信息处理。
# 主机名注册的是 futurebackrookie.github.io —— 账号级域名，名下其它
# GitHub Pages 项目的流量会一起算进来，后台按 /swaylume-site/* 路径筛才是本站数字。
ANALYTICS = ("cloudflare", "aca979be3ab8462e811dcefcae9aa19b")

ROOT = pathlib.Path(__file__).parent
PLACEHOLDER = re.compile(r"\{\{([\w.\-]+)\}\}")


def load_locales():
    out = {}
    for code in LOCALES:
        path = ROOT / "locales" / f"{code}.json"
        if not path.exists():
            print(f"❌ 缺少 locales/{code}.json")
            sys.exit(1)
        out[code] = json.loads(path.read_text())
    return out


def check_keys(locales, template):
    """每种语言的词条集合必须完全一致，且覆盖模板里的每个占位符。

    漏一条的后果不是报错而是页面上突兀地冒出一句中文，肉眼很难在
    五个语言 × 十个分节里发现 —— 所以必须机器查。
    """
    used = set(PLACEHOLDER.findall(template))
    base = set(locales[DEFAULT])
    errors = []

    # js.* 不以 {{}} 形式出现在模板里 —— 它们注入到 window.__I18N 供页面脚本读取，
    # 所以「模板里没用到」对它们不是错误。
    # 这几条由 build.py 自己消费，模板里不会出现对应的 {{}}：
    # 前两条进 <head>，trust.analytics 只在开了统计时才输出。
    CODE_KEYS = {"x.title1", "meta.description", "trust.analytics"}
    # 豁免名单最容易变成孤儿词条的藏身处 —— 写进来却没人用，检查照样放行。
    # 所以反过来验一遍：豁免的 key 必须真的被本文件用到。
    #
    # 注意这里必须数**出现次数**，不能只判断「在不在源码里」：
    # CODE_KEYS 这行本身就写着这些 key，源码里永远找得到，那样写出来的
    # 检查永远不会失败。第一版就是这么写的，拿一个纯属虚构的 key 去测才发现。
    # 声明处贡献 1 次，所以真正被用到的至少出现 2 次。
    _self = pathlib.Path(__file__).read_text()
    _dead = {k for k in CODE_KEYS if _self.count(f'"{k}"') < 2}
    if _dead:
        errors.append(f"豁免名单里有 build.py 根本没用到的 key：{sorted(_dead)}")
    missing_in_template = {k for k in base - used
                           if not k.startswith("js.") and k not in CODE_KEYS}
    if missing_in_template:
        errors.append(f"{DEFAULT} 有 {len(missing_in_template)} 条词条模板里用不到："
                      f"{sorted(missing_in_template)[:5]}")

    # 但 js.* 必须真的被脚本用到，否则就是改代码时留下的孤儿词条
    import re as _re
    referenced = set(_re.findall(r'T\("([\w.]+)"\)', template))
    referenced |= {f"js.preview{n}.{f}" for n in "1234" for f in ("kind", "title", "meta")}
    referenced |= {f"js.gov{n}.{f}" for n in "1234567" for f in ("p", "m")}
    orphan = {k for k in base if k.startswith("js.")} - referenced
    if orphan:
        errors.append(f"js.* 有 {len(orphan)} 条没有任何脚本引用：{sorted(orphan)}")
    unknown = used - base
    if unknown:
        errors.append(f"模板里有 {len(unknown)} 个占位符没有对应词条："
                      f"{sorted(unknown)[:5]}")

    for code, entries in locales.items():
        if code == DEFAULT:
            continue
        miss = base - set(entries)
        extra = set(entries) - base
        if miss:
            errors.append(f"{code} 缺 {len(miss)} 条：{sorted(miss)[:6]}")
        if extra:
            errors.append(f"{code} 多出 {len(extra)} 条：{sorted(extra)[:6]}")
        empty = [k for k, v in entries.items() if not str(v).strip()]
        if empty:
            errors.append(f"{code} 有 {len(empty)} 条是空的：{empty[:6]}")

    return errors


def analytics_tag():
    """无 cookie 的访问统计。没配置就什么都不输出。

    defer 是必须的：统计脚本绝不该挡住首屏那个着色器的渲染。
    """
    if not ANALYTICS:
        return []
    kind, key = ANALYTICS
    if kind == "cloudflare":
        return ['<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
                f"""data-cf-beacon='{{"token": "{key}"}}'></script>"""]
    if kind == "goatcounter":
        return [f'<script defer data-goatcounter="https://{key}.goatcounter.com/count" '
                'src="//gc.zgo.at/count.js"></script>']
    raise ValueError(f"不认识的统计方案：{kind}")


def analytics_note(entries):
    """开了统计才输出这句话。"""
    if not ANALYTICS:
        return ""
    return f'<p class="trust-note rise">{entries["trust.analytics"]}</p>'


def head(code, entries):
    subdir, lang, og_locale, _ = LOCALES[code]
    canonical = f"{SITE_URL}/{subdir}/" if subdir else f"{SITE_URL}/"
    lines = [
        "<!doctype html>",
        f'<html lang="{lang}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        f'<title>{entries["x.title1"]}</title>',
        f'<meta name="description" content="{entries["meta.description"]}">',
        f'<meta name="google-site-verification" content="{GOOGLE_SITE_VERIFICATION}">',
        f'<link rel="canonical" href="{canonical}">',
    ]
    # hreflang：告诉搜索引擎这几个页面是同一内容的不同语言版本。
    # 少了它，各语言版本会被当成互相抄袭的重复内容。
    for other, (osub, olang, _, _) in LOCALES.items():
        href = f"{SITE_URL}/{osub}/" if osub else f"{SITE_URL}/"
        lines.append(f'<link rel="alternate" hreflang="{olang}" href="{href}">')
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/">')
    lines += [
        '<meta name="theme-color" content="#08070E" media="(prefers-color-scheme: dark)">',
        '<meta name="theme-color" content="#F2F1F7" media="(prefers-color-scheme: light)">',
        f'<meta property="og:title" content="{entries["x.title1"]}">',
        f'<meta property="og:description" content="{entries["meta.description"]}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:locale" content="{og_locale}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:image" content="{SITE_URL}/og-cover.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta name="twitter:card" content="summary_large_image">',
        # downloadUrl 必须指向公开仓库；源码仓库是私有的，写进去等于喂死链
        '<script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"SoftwareApplication","name":"Swaylume",'
        '"applicationCategory":"UtilitiesApplication","operatingSystem":"macOS 14 or later",'
        '"softwareVersion":"Beta",'
        '"downloadUrl":"https://github.com/futurebackrookie/swaylume-site/releases",'
        '"offers":{"@type":"Offer","price":"0","priceCurrency":"USD"}}</script>',
        f'<link rel="icon" type="image/png" href="{SITE_URL}/icon.png">',
        f'<link rel="apple-touch-icon" href="{SITE_URL}/icon.png">',
    ]
    lines += analytics_tag()
    lines += [
        "</head>",
        "<body>",
    ]
    return "\n".join(lines)


def lang_switcher(code):
    """语言切换器。用真实 <a> 而不是 JS 下拉 —— 爬虫要能顺着链接找到其它语言版本。"""
    items = []
    for other, (subdir, lang, _, name) in LOCALES.items():
        href = f"/{subdir}/" if subdir else "/"
        # GitHub Pages 部署在子路径下，用相对根路径会跑到域名根部
        base = "/" + SITE_URL.rstrip("/").split("/")[-1] if "github.io" in SITE_URL else ""
        href = f"{base}{href}"
        current = ' aria-current="true"' if other == code else ""
        items.append(f'<a href="{href}" hreflang="{lang}" lang="{lang}"{current}>{name}</a>')
    return ('<div class="langs" role="group" aria-label="Language">'
            + "".join(items) + "</div>")


def render(template, entries, code):
    def rep(m):
        key = m.group(1)
        if key not in entries:
            raise KeyError(f"{code}: 缺词条 {key}")
        return str(entries[key])
    out = PLACEHOLDER.sub(rep, template)
    # 正文里的资源引用必须换成绝对地址。语言页在 /en/ /ja/ 等子目录下，
    # 相对路径会解析到子目录里去 —— 根页面正常、四个语言页全裂图，
    # 只测根页面永远发现不了。
    out = out.replace("%%SITE%%", SITE_URL)
    out = out.replace("<!--LANG-SWITCHER-->", lang_switcher(code))
    # 站点自己的访问统计声明。关掉统计时输出空串 —— 页面上有一整节在讲隐私，
    # 挂了计数器却只字不提，被人打开开发者工具看见就是自打嘴巴；
    # 反过来，没挂统计还写着「本站使用统计」同样是假话。所以跟着开关走。
    out = out.replace("<!--SITE-ANALYTICS-NOTE-->", analytics_note(entries))
    # 页面脚本要用的文案单独注入。JS 里写死中文的话，切到别的语言后
    # 交互部分（层级读数、调速器日志、精选卡片）会突然变回中文。
    js_strings = {k: v for k, v in entries.items() if k.startswith("js.")}
    blob = json.dumps(js_strings, ensure_ascii=False, separators=(",", ":"))
    out = out.replace("<!--I18N-DATA-->",
                      f"<script>window.__I18N={blob};</script>")
    return out


def content_mtime():
    """内容最后改动时间。

    用构建时间当 lastmod 会在每次重新生成时都变一遍，等于反复告诉搜索引擎
    「内容更新了」，久了就不被当真。取模板和词条文件的最新修改时间才是实话。
    """
    import datetime
    files = [ROOT / "template.html"] + sorted((ROOT / "locales").glob("*.json"))
    newest = max(f.stat().st_mtime for f in files if f.exists())
    return datetime.date.fromtimestamp(newest).isoformat()


def write_sitemap():
    """多语言 sitemap：每条 URL 都要列出全部语言版本（含它自己）。

    只列 5 个 <loc> 而不带 xhtml:link 的话，搜索引擎不知道它们是同一内容的
    不同语言，可能当成互相重复的页面。
    """
    lastmod = content_mtime()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
             '        xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    def url_of(subdir):
        return f"{SITE_URL}/{subdir}/" if subdir else f"{SITE_URL}/"
    for code, (subdir, lang, _, _) in LOCALES.items():
        lines.append("  <url>")
        lines.append(f"    <loc>{url_of(subdir)}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        for other, (osub, olang, _, _) in LOCALES.items():
            lines.append(f'    <xhtml:link rel="alternate" hreflang="{olang}" '
                         f'href="{url_of(osub)}"/>')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" '
                     f'href="{url_of("")}"/>')
        lines.append("  </url>")
    lines.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n")
    return lastmod


def write_robots():
    """robots.txt。

    ⚠️ 部署在 github.io 的子路径下时，爬虫**只认域名根部**的 robots.txt，
    /swaylume-site/robots.txt 会被忽略。生成它是为了将来绑自定义域名时
    自动生效；在那之前，让 sitemap 被发现的办法是去 Search Console 提交。
    """
    (ROOT / "robots.txt").write_text(
        "User-agent: *\n"
        "Allow: /\n\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n")


def main():
    template = (ROOT / "template.html").read_text()
    locales = load_locales()

    errors = check_keys(locales, template)
    if errors:
        print("❌ 词条校验不通过：")
        for e in errors:
            print("  " + e)
        return 1

    if "--check" in sys.argv:
        print(f"✅ 词条校验通过（{len(LOCALES)} 种语言 × {len(locales[DEFAULT])} 条）")
        return 0

    for code, (subdir, _, _, _) in LOCALES.items():
        body = render(template, locales[code], code)
        doc = head(code, locales[code]) + "\n" + body + "\n</body>\n</html>\n"
        target = ROOT / subdir / "index.html" if subdir else ROOT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(doc)
        if code == DEFAULT:
            # 预览片段自带 title/description；完整文档里这两项由 head() 负责，
            # 两边都放会产生两个 <title>。
            e = locales[code]
            (ROOT / "content.html").write_text(
                f'<title>{e["x.title1"]}</title>\n'
                f'<meta name="description" content="{e["meta.description"]}">\n\n'
                + body)
        rel = f"{subdir}/index.html" if subdir else "index.html"
        print(f"  {rel:20} {len(doc):>7,} 字节  {code}")

    lastmod = write_sitemap()
    write_robots()
    print(f"  sitemap.xml         {len(LOCALES)} 条 URL  lastmod {lastmod}")
    print(f"  robots.txt          （子路径部署下爬虫不读，绑域名后自动生效）")
    print(f"✅ {len(LOCALES)} 种语言生成完毕")
    return 0


if __name__ == "__main__":
    sys.exit(main())
