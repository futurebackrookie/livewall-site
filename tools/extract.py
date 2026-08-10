#!/usr/bin/env python3
"""一次性脚本：把 content.html 拆成 template.html + locales/zh-Hans.json。

抽取粒度是关键。按标签切会把
    <p>跑在 macOS <strong>桌面图标之下</strong>，点击穿透</p>
切成三段互不相干的碎片 —— 各语言语序不同，拼回去必然是病句。
所以规则是：**在「最内层直接含中文的元素」上取整个 innerHTML**，
行内标签留在词条里，翻译时可以把强调放到该放的位置。

跑完用 build.py 重新生成，必须和原 content.html 逐字节一致才算抽对了。
"""
import json, re, pathlib, sys

# 行内标签留在词条内部；块级标签是抽取边界
INLINE = {"strong", "b", "em", "i", "code", "small", "span", "a", "br", "sup", "sub"}
VOID = {"br", "img", "meta", "link", "input", "hr", "source", "path", "rect",
        "circle", "polygon", "line", "ellipse", "use", "stop"}
# 整块跳过：里面是代码/图形，不翻译（代码块里的中文注释单独处理）
SKIP_SUBTREE = {"script", "style", "svg"}

CJK = re.compile(r"[一-鿿぀-ヿ]")
TAG = re.compile(r"<(/?)([a-zA-Z][\w-]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*?)(/?)>", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def tokenize(html):
    """切成 (kind, raw, name, attrs) 序列，raw 保留原始文本以便无损还原。"""
    out, pos = [], 0
    # 注释先占位：源码注释不是给用户看的，不能变成待翻词条
    spans = [(m.start(), m.end(), m.group(0)) for m in COMMENT.finditer(html)]
    def in_comment(i):
        return any(a <= i < b for a, b, _ in spans)
    for m in TAG.finditer(html):
        if in_comment(m.start()):
            continue
        if m.start() > pos:
            out.append(("text", html[pos:m.start()], None, None))
        slash, name, attrs, selfclose = m.groups()
        name = name.lower()
        if slash:
            kind = "close"
        elif selfclose or name in VOID:
            kind = "void"
        else:
            kind = "open"
        out.append((kind, m.group(0), name, attrs))
        pos = m.end()
    if pos < len(html):
        out.append(("text", html[pos:], None, None))
    return out


def build_tree(tokens):
    root = {"name": None, "raw_open": "", "children": [], "parent": None}
    stack = [root]
    skip_depth = 0
    for kind, raw, name, attrs in tokens:
        node = stack[-1]
        if skip_depth:
            node["children"].append({"name": "#raw", "raw": raw})
            if kind == "open" and name in SKIP_SUBTREE:
                skip_depth += 1
            elif kind == "close" and name in SKIP_SUBTREE:
                skip_depth -= 1
            continue
        if kind == "text":
            node["children"].append({"name": "#text", "raw": raw})
        elif kind == "void":
            node["children"].append({"name": name, "raw": raw, "void": True})
        elif kind == "open":
            if name in SKIP_SUBTREE:
                node["children"].append({"name": "#raw", "raw": raw})
                skip_depth = 1
                continue
            child = {"name": name, "raw_open": raw, "attrs": attrs or "",
                     "children": [], "parent": node}
            node["children"].append(child)
            stack.append(child)
        else:  # close
            # 容错：遇到不匹配的闭标签就原样塞回去，别把树搞乱
            for i in range(len(stack) - 1, 0, -1):
                if stack[i]["name"] == name:
                    stack[i]["raw_close"] = raw
                    del stack[i + 1:]
                    stack.pop()
                    break
            else:
                node["children"].append({"name": "#raw", "raw": raw})
    return root


def inner_html(node):
    parts = []
    for c in node["children"]:
        if c["name"] in ("#text", "#raw") or c.get("void"):
            parts.append(c["raw"])
        else:
            parts.append(c.get("raw_open", "") + inner_html(c) + c.get("raw_close", ""))
    return "".join(parts)


def has_cjk(node):
    return bool(CJK.search(inner_html(node)))


def only_anchor_children(node):
    """子元素全是 <a>（其余只有空白）—— 导航、页脚、链接网格属于这类，
    每个 <a> 各自成条，否则 href 会被复制进五份语言文件。"""
    els = [c for c in node["children"] if c["name"] not in ("#text", "#raw")]
    if len(els) < 2 or any(c["name"] != "a" for c in els):
        return False
    return all(not c["raw"].strip() for c in node["children"] if c["name"] == "#text")


class Extractor:
    def __init__(self):
        self.entries = {}
        self.counter = {}

    def key_for(self, node):
        sec = ""
        p = node
        while p:
            a = p.get("attrs", "") or ""
            m = re.search(r'id="([\w-]+)"', a)
            if m and p["name"] in ("section", "header", "nav", "footer"):
                sec = m.group(1)
                break
            p = p.get("parent")
        base = f"{sec or 'x'}.{node['name']}"
        self.counter[base] = self.counter.get(base, 0) + 1
        return f"{base}{self.counter[base]}"

    def walk(self, node):
        """返回该节点的模板 innerHTML。"""
        # 子元素全是 <a>：逐个抽
        if only_anchor_children(node):
            parts = []
            for c in node["children"]:
                if c["name"] in ("#text", "#raw") or c.get("void"):
                    parts.append(c["raw"])
                elif has_cjk(c):
                    k = self.key_for(c)
                    self.entries[k] = inner_html(c)
                    parts.append(c["raw_open"] + "{{" + k + "}}" + c.get("raw_close", ""))
                else:
                    parts.append(c.get("raw_open", "") + self.walk(c) + c.get("raw_close", ""))
            return "".join(parts)

        child_els = [c for c in node["children"]
                     if c["name"] not in ("#text", "#raw") and not c.get("void")]
        block_children = [c for c in child_els if c["name"] not in INLINE]
        # #raw 是 svg/script 这类整块跳过的内容。它必须算块级边界 ——
        # 否则 <div><svg 一大堆 path/><span>项目</span></div> 会把
        # 整段 path 数据当成待翻文本，复制进每一种语言。
        if any(c["name"] == "#raw" and c["raw"].strip() for c in node["children"]):
            block_children = block_children + ["#raw"]

        # 没有块级子元素、且自己含中文 -> 就在这一层抽，行内标签留在词条里
        if not block_children and has_cjk(node) and node["name"] is not None:
            k = self.key_for(node)
            self.entries[k] = inner_html(node)
            return "{{" + k + "}}"

        parts = []
        for c in node["children"]:
            if c["name"] in ("#text", "#raw") or c.get("void"):
                # 块级容器里散落的中文文本（少见但要接住）
                if (c["name"] == "#text" and CJK.search(c["raw"]) and c["raw"].strip()
                        and not c["raw"].strip().startswith("<!--")):
                    lead = re.match(r"\s*", c["raw"]).group(0)
                    trail = re.search(r"\s*$", c["raw"]).group(0)
                    body = c["raw"].strip()
                    self.counter.setdefault("loose", 0)
                    self.counter["loose"] += 1
                    k = f"loose.t{self.counter['loose']}"
                    self.entries[k] = body
                    parts.append(lead + "{{" + k + "}}" + trail)
                else:
                    parts.append(c["raw"])
            else:
                parts.append(c.get("raw_open", "") + self.walk(c) + c.get("raw_close", ""))
        return "".join(parts)


def main():
    src = pathlib.Path("content.html")
    html = src.read_text()

    tree = build_tree(tokenize(html))
    ex = Extractor()
    template = ex.walk(tree)

    # 需要翻译的属性
    def sub_attr(pattern, keyname):
        nonlocal template
        def rep(m):
            val = m.group(2)
            if not CJK.search(val):
                return m.group(0)
            ex.entries[keyname] = val
            return m.group(1) + "{{" + keyname + "}}" + m.group(3)
        template = re.sub(pattern, rep, template, count=1)

    sub_attr(r'(<title>)(.*?)(</title>)', "meta.title")
    sub_attr(r'(<meta name="description" content=")([^"]*)(">)', "meta.description")

    pathlib.Path("template.html").write_text(template)
    pathlib.Path("locales").mkdir(exist_ok=True)
    pathlib.Path("locales/zh-Hans.json").write_text(
        json.dumps(ex.entries, ensure_ascii=False, indent=2) + "\n")

    print(f"抽出 {len(ex.entries)} 条词条")
    print(f"模板 {len(template)} 字节，残留中文 {len(CJK.findall(re.sub(r'{{[^}]+}}', '', template)))} 字")
    return 0


if __name__ == "__main__":
    sys.exit(main())
