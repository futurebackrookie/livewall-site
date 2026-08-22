#!/usr/bin/env python3
"""官网访问统计。

后台（dash.cloudflare.com → Web Analytics）一次只能看一个时间窗口，想知道
「接上统计以来一共多少」得手动点日期，还看不到按天的原始数字。这个脚本一次
把总量、按天曲线、来源国家和热门路径全拉下来。

需要一个 **API token**。页面里那个 beacon token 读不了数据 —— 它只负责标识
「这些访问算哪个站」，两者完全不是一回事：
    https://dash.cloudflare.com/profile/api-tokens → Custom token
    权限只勾 Account → Account Analytics → Read

用法：
    CLOUDFLARE_API_TOKEN=xxx python3 site/tools/analytics.py [天数，默认 30]
    CF_ACCOUNT_ID=xxx  # 可选，跳过账号自动探测

token 只从环境变量读，不写进文件、不进版本库。它能读整个账号的统计，
和 build.py 里那个公开的 beacon token 不是一个安全级别。

统计是 2026-08-17 接上的，再往前查一律是 0，不是脚本坏了。
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402  —— site tag 只在 build.py 里定义一份，别在这儿再抄一遍

API = "https://api.cloudflare.com/client/v4"
# 后台把站点按主机名注册，而 futurebackrookie.github.io 是账号级域名。
# 目前只有官网页面带 beacon，所以数字就是官网的；但哪天别的项目也挂上同一个
# token，总量就会串味 —— 所以下面额外按路径拆一份出来。
SITE_PREFIX = "/swaylume-site/"


def token():
    t = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    if not t or "你的token" in t or "YOUR_TOKEN" in t:
        sys.exit("需要 CLOUDFLARE_API_TOKEN（权限：Account → Account Analytics → Read）。\n"
                 "去 https://dash.cloudflare.com/profile/api-tokens 建一个。")
    return t


def call(url, tok, payload=None):
    """发一次请求，把 Cloudflare 的错误翻译成人话。

    401/403 时 urllib 会抛 HTTPError，而错误原因在响应体里 —— 不读出来的话
    只能看到一句 'HTTP Error 400: Bad Request'，完全不知道是 token 错了
    还是权限少了。
    """
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
    })
    try:
        raw = urllib.request.urlopen(req, timeout=30).read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
    except urllib.error.URLError as e:
        sys.exit(f"连不上 Cloudflare：{e.reason}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        sys.exit(f"Cloudflare 没返回 JSON：{raw[:300]}")


def account_id(tok):
    if os.environ.get("CF_ACCOUNT_ID"):
        return os.environ["CF_ACCOUNT_ID"]
    d = call(f"{API}/accounts", tok)
    if not d.get("success"):
        msgs = "; ".join(e.get("message", str(e)) for e in (d.get("errors") or [])) or "未知错误"
        sys.exit(f"取账号列表失败：{msgs}\n→ token 无效或权限不足（需要 Account Analytics → Read）。")
    r = d.get("result") or []
    if not r:
        sys.exit("这个 token 看不到任何账号；用 CF_ACCOUNT_ID=xxx 手动指定。")
    return r[0]["id"]


def query(tok, acct, site_tag, since, until, with_paths=True):
    flt = f'{{siteTag: "{site_tag}", datetime_geq: "{since}", datetime_leq: "{until}"}}'
    paths = f"""
      paths: rumPageloadEventsAdaptiveGroups(
        filter: {flt}, limit: 20, orderBy: [count_DESC]
      ) {{ count sum {{ visits }} dimensions {{ requestPath }} }}""" if with_paths else ""
    gql = f"""query {{
  viewer {{
    accounts(filter: {{accountTag: "{acct}"}}) {{
      total: rumPageloadEventsAdaptiveGroups(filter: {flt}, limit: 1) {{
        count sum {{ visits }}
      }}
      daily: rumPageloadEventsAdaptiveGroups(
        filter: {flt}, limit: 100, orderBy: [date_ASC]
      ) {{ count sum {{ visits }} dimensions {{ date }} }}
      countries: rumPageloadEventsAdaptiveGroups(
        filter: {flt}, limit: 10, orderBy: [count_DESC]
      ) {{ count dimensions {{ countryName }} }}{paths}
    }}
  }}
}}"""
    return call(f"{API}/graphql", tok, {"query": gql})


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    kind, site_tag = build.ANALYTICS
    if kind != "cloudflare":
        sys.exit(f"build.py 里配的是 {kind}，这个脚本只会读 Cloudflare。")

    tok = token()
    acct = account_id(tok)
    until = datetime.now(timezone.utc)
    since = until - timedelta(days=days)
    fmt = "%Y-%m-%dT%H:%M:%SZ"

    d = query(tok, acct, site_tag, since.strftime(fmt), until.strftime(fmt))
    # requestPath 这个维度名没在真实账号上验证过。万一 schema 里不叫这个，
    # 整个查询会一起失败 —— 与其什么都看不到，不如去掉这块重来一次。
    if d.get("errors"):
        d = query(tok, acct, site_tag, since.strftime(fmt), until.strftime(fmt), with_paths=False)
        if d.get("errors"):
            sys.exit("查询出错：" + json.dumps(d["errors"], ensure_ascii=False, indent=2))
        print("⚠️  按路径拆分不可用（API 不认 requestPath），只显示站点总量。\n")

    accounts = (d.get("data") or {}).get("viewer", {}).get("accounts") or []
    if not accounts:
        sys.exit("账号下没查到这个 site tag 的数据。确认后台的站点就是 " + site_tag)
    a = accounts[0]

    t = a["total"][0] if a["total"] else {"count": 0, "sum": {"visits": 0}}
    print(f"最近 {days} 天：{t['count']} 次页面浏览 / {t['sum']['visits']} 次访问")
    if not t["count"]:
        print("（0 未必是错的：统计 2026-08-17 才接上。）")

    if a.get("paths"):
        mine = [p for p in a["paths"] if p["dimensions"]["requestPath"].startswith(SITE_PREFIX)]
        views = sum(p["count"] for p in mine)
        visits = sum(p["sum"]["visits"] for p in mine)
        print(f"其中官网（{SITE_PREFIX}*）：{views} 次浏览 / {visits} 次访问")

    print("\n按天：")
    for r in a["daily"]:
        print(f"  {r['dimensions']['date']}  浏览 {r['count']:>5}  访问 {r['sum']['visits']:>5}")

    if a["countries"]:
        print("\n来源国家 Top10：")
        for r in a["countries"]:
            print(f"  {r['dimensions']['countryName']:<20} {r['count']}")

    if a.get("paths"):
        print("\n热门路径：")
        for p in a["paths"][:10]:
            print(f"  {p['dimensions']['requestPath']:<40} {p['count']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
