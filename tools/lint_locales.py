#!/usr/bin/env python3
"""语言文件体检。

翻译最容易出的不是措辞问题，而是这三类机器能查、人眼很难在
5 种语言 × 180 条里发现的问题：

1. **语言串味**：日语里混进简体字（帧率 / 设置），或英德法里混进汉字。
2. **HTML 结构漂移**：某一版少了 </strong>，或 href 被顺手"翻译"掉了。
3. **占位符不匹配**：某一版少了一条，页面上就会突兀地冒出一句中文。

用法：python3 tools/lint_locales.py
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).parent.parent
BASE = "zh-Hans"

# 只列**日语里字形不同**的简体字。
#
# 共用汉字绝对不能进这个集合：数 号 来 性 示 面 理 属 壁 紙 動 画 音 声 点 用 …
# 都是标准日语，误列进来会把正确的译文报成错误 —— 前两版就是这么翻车的，
# 而且报了一屏假警报，差点让人以为整份日语文件都是中文。
#
# 判据：该字在日语里有对应的新字体/旧字体写法（括号内），或日语根本不用。
SIMPLIFIED_ONLY = set(
    "这么们够浏帧"                  # 日语完全不用（这→この）
    "说时网图电页边长门问题"        # 説 時 網 図 電 頁 辺 長 門 問 題
    "现应对语验证转换开关设备"      # 現 応 対 語 験 証 転 換 開 関 設 備
    "载击测导览样输选择项级别读"    # 載 撃 測 導 覧 様 輸 選 択 項 級 別 読
    "软广启务终结试确认贝纸动"      # 軟 広 啓 務 終 結 試 確 認 貝 紙 動
    "传递维护闭纹层窗还极丽单"      # 伝 逓 維 護 閉 紋 層 窓 還 極 麗 単
    "户处显视频类组织统计错误"      # 戸 処 顕 視 頻 類 組 織 統 計 錯 誤
    "无论虽实际经过"                # 無 論 雖 実 際 経 過
)
# 英/德/法里出现任何汉字或假名都是可疑的

# 自我保护：这个集合里出现假名或全角标点，一定是注解误写进了字符串。
# 上一版就是 "这（この）" 让 こ/の 进了集合，结果每条带 の 的日语全被误报。
_bad = [c for c in SIMPLIFIED_ONLY if "\u3040" <= c <= "\u30ff" or c in "（）、。"]
assert not _bad, f"字表里混进了假名或标点：{_bad}"

CJK_ANY = re.compile(r"[぀-ヿ一-鿿]")
LATIN_LOCALES = {"en", "de", "fr"}


def main():
    files = sorted((ROOT / "locales").glob("*.json"))
    if not files:
        print("❌ locales/ 下没有语言文件")
        return 1

    data = {p.stem: json.loads(p.read_text()) for p in files}
    if BASE not in data:
        print(f"❌ 缺少基准语言 {BASE}")
        return 1

    base_keys = set(data[BASE])
    problems = []

    for code, entries in sorted(data.items()):
        # ---- 词条集合 ----
        miss = base_keys - set(entries)
        extra = set(entries) - base_keys
        if miss:
            problems.append(f"[{code}] 缺 {len(miss)} 条：{sorted(miss)[:6]}")
        if extra:
            problems.append(f"[{code}] 多 {len(extra)} 条：{sorted(extra)[:6]}")

        for key in sorted(base_keys & set(entries)):
            src, dst = str(data[BASE][key]), str(entries[key])

            # ---- HTML 结构 ----
            if sorted(re.findall(r"<(\w+)", src)) != sorted(re.findall(r"<(\w+)", dst)):
                problems.append(f"[{code}] {key} 标签数量与基准不一致")
            if re.findall(r'href="([^"]+)"', src) != re.findall(r'href="([^"]+)"', dst):
                problems.append(f"[{code}] {key} href 被改动了")
            # split 特效要求 data-t 与内容一致，否则色差层会错位
            for attr, text in re.findall(r'data-t="([^"]*)"[^>]*>([^<]*)<', dst):
                if attr != text:
                    problems.append(f"[{code}] {key} data-t=\"{attr}\" 与内容 \"{text}\" 不一致")

            # ---- 语言串味 ----
            if code == "ja":
                bad = sorted(set(dst) & SIMPLIFIED_ONLY)
                if bad:
                    problems.append(f"[ja] {key} 混入简体字 {''.join(bad)}")
            if code in LATIN_LOCALES:
                if CJK_ANY.search(dst):
                    got = "".join(sorted(set(CJK_ANY.findall(dst))))
                    problems.append(f"[{code}] {key} 混入汉字/假名 {got}")

            # ---- 空值 ----
            if not dst.strip():
                problems.append(f"[{code}] {key} 是空的")

    if problems:
        print(f"❌ {len(problems)} 处问题：")
        for p in problems[:60]:
            print("  " + p)
        if len(problems) > 60:
            print(f"  …还有 {len(problems) - 60} 处")
        return 1

    print(f"✅ {len(data)} 种语言 × {len(base_keys)} 条，全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
