#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
五大平台真实热度聚合器 → heat.json（v2）
=========================================
数据源（2026-10-30 逆向验证，均为平台官方真实数据）：
  腾讯视频  getSearchHotListHttp                    → HotLevel 数值热度
  爱奇艺    www.iqiyi.com/ranks1PCW/home SSR        → 实时热度数值 (rvi__index__num)
  优酷      www.youku.com/ku/rank __INITIAL_DATA__  → 官方榜单条目(+热度门槛"最高热度破X")
  芒果TV    dc.bz.mgtv.com module/infos 官方热播模块 → 官方榜位 (item.name)
  B站       api.bilibili.com ranking/v2 (spi换buvid) → 全站榜单+播放量
"""
import json
import math
import re
import sys
from datetime import datetime
from html import unescape

import requests

sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      "Accept-Language": "zh-CN,zh;q=0.9"}


# --------------------------------------------------------------- 腾讯视频
def fetch_tencent():
    url = ("https://pbaccess.video.qq.com/trpc.tencentvideohotlistdata.hotlistdata."
           "DoSearchHotListHttp/getSearchHotListHttp")
    seen, out = set(), []
    for cid, name in [(0, "全站"), (1, "电影"), (2, "电视剧"), (10, "综艺"), (3, "动漫")]:
        try:
            r = requests.get(url, params={"ChannelID": cid, "PageSize": 30, "PageNum": 0,
                                          "SceneID": 2},
                             headers={**UA, "Referer": "https://v.qq.com/"}, timeout=15)
            d = r.json()["data"]["Results"][0]["Result"]
            for it in (d.get("ListInfo") or []):
                t = it.get("Query", "")
                if not t or t in seen:
                    continue
                seen.add(t)
                out.append({"title": t, "heat": int(it.get("HotLevel", 0)), "type": name,
                            "cid": it.get("ID", ""),
                            "url": f"https://v.qq.com/x/cover/{it.get('ID','')}.html"})
        except Exception as e:
            print("  tencent", name, "FAIL", e)
    return out[:60]


# --------------------------------------------------------------- 爱奇艺
def fetch_iqiyi():
    try:
        r = requests.get("https://www.iqiyi.com/ranks1PCW/home?v=17.104.26764",
                         headers=UA, timeout=15)
        r.encoding = "utf-8"
        t = r.text
        out = []
        # 每个榜单项是一个 <a class="rvi__box ..."> 块
        for blk in re.split(r'<a [^>]*class="rvi__box', t)[1:]:
            mt = re.search(r'class="rvi__tit1"[^>]*>(?:<span[^>]*>\d+</span>)?([^<]+)', blk)
            mh = re.search(r'rvi__index__num[^>]*>(\d+)</span>', blk)
            mc = re.search(r'class="rvi__tag rvi__tag1"[^>]*>([^<]+)</span>', blk)
            mu = re.search(r'href="([^"]+)"', blk)
            if mt and mh:
                out.append({"title": unescape(mt.group(1)).strip(),
                            "heat": int(mh.group(1)),
                            "type": (unescape(mc.group(1)).strip() if mc else "实时热度"),
                            "url": ("https:" + mu.group(1) if mu and mu.group(1).startswith("//") else "")})
        seen, dedup = set(), []
        for it in out:
            if it["title"] in seen:
                continue
            seen.add(it["title"])
            dedup.append(it)
        return dedup[:30]
    except Exception as e:
        print("  iqiyi FAIL", e)
        return []


# --------------------------------------------------------------- 优酷
def _walk(node, out):
    """按文档序收集榜单条目：title(str) 与 recInfo/reason 同级的字典。"""
    if isinstance(node, dict):
        if isinstance(node.get("title"), str) and node.get("title") and \
                ("recInfo" in node or "reason" in node):
            out.append(node)
        for v in node.values():
            _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)


def fetch_youku():
    try:
        r = requests.get("https://www.youku.com/ku/rank", headers=UA, timeout=20)
        r.encoding = "utf-8"
        t = r.text
        m = re.search(r'window\.__INITIAL_DATA__\s*=\s*(\{.*?\});\s*</script>', t, re.S)
        if not m:
            print("  youku: no __INITIAL_DATA__")
            return []
        # 页面数据岛是 JS 字面量，裸 undefined 不是合法 JSON → 置 null
        data = json.loads(m.group(1).replace(":undefined", ":null"))
        items = []
        _walk(data, items)
        out, seen = [], set()
        for it in items:
            title = it.get("title") or ""
            if not title or title in seen:
                continue
            seen.add(title)
            reason = it.get("reason") or {}
            rtxt = ((reason.get("text") or {}).get("title")) or ""
            heat = 0
            mh = re.search(r'最高热度破(\d+)', rtxt)
            if mh:
                heat = int(mh.group(1))
            mr = re.search(r'([\u4e00-\u9fa5A-Za-z0-9]{2,10}榜)TOP(\d+)', rtxt)
            typ = mr.group(1) if mr else ("热度门槛" if heat else "推荐位")
            rank = int(mr.group(2)) if mr else len(out) + 1
            out.append({"title": title, "heat": heat, "rank": rank, "type": typ,
                        "url": f"https://www.youku.com/show-page?showId="})
        return out[:30]
    except Exception as e:
        print("  youku FAIL", e)
        return []


# --------------------------------------------------------------- 芒果TV
def fetch_mgtv():
    try:
        u = ("https://dc.bz.mgtv.com/dynamic/v1/module/infos/webdid/9.0.9/10.0/10000000/"
             "space/0/4/4/7942,3428,1269,1272,1271,1270?osType=window&device=pc")
        d = requests.get(u, headers=UA, timeout=15).json()
        out, seen = [], set()
        for mod in d.get("data", []):
            mtitle = mod.get("moduleTitle") or "芒果热播"
            for dsl in mod.get("DSLList", []):
                for it in ((dsl.get("data") or {}).get("items") or []):
                    n = it.get("name") or ""
                    if not n or n in seen:
                        continue
                    seen.add(n)
                    out.append({"title": n, "heat": 0, "rank": len(out) + 1,
                                "type": mtitle,
                                "url": it.get("videoUrl") or ""})
        return out[:30]
    except Exception as e:
        print("  mgtv FAIL", e)
        return []


# --------------------------------------------------------------- B站
def fetch_bilibili():
    try:
        s = requests.Session()
        s.headers.update(UA)
        spi = s.get("https://api.bilibili.com/x/frontend/finger/spi", timeout=15,
                    headers={"Referer": "https://www.bilibili.com/"}).json()
        b3 = (spi.get("data") or {}).get("b_3", "")
        b4 = (spi.get("data") or {}).get("b_4", "")
        if b3:
            s.cookies.set("buvid3", b3, domain=".bilibili.com")
            s.cookies.set("buvid4", b4, domain=".bilibili.com")
        r = s.get("https://api.bilibili.com/x/web-interface/popular?ps=50&pn=1", timeout=15)
        d = r.json()
        if d.get("code") != 0:
            print("  bilibili code:", d.get("code"))
            return []
        out = []
        for i, v in enumerate((d.get("data") or {}).get("list") or [], 1):
            stat = v.get("stat") or {}
            out.append({"title": v.get("title", ""), "heat": int(stat.get("view", 0)),
                        "rank": i, "type": v.get("tname", "") or "热门",
                        "url": v.get("short_link_v2") or f"https://www.bilibili.com/video/av{v.get('aid','')}"})
        return out[:30]
    except Exception as e:
        print("  bilibili FAIL", e)
        return []


# --------------------------------------------------------------- 统一算法
STOP = re.compile(r"[\s：:·，,。.·\-—_()（）\[\]【】!！?？'’\"“”“]+")
SEASON = re.compile(r"(第[一二三四五六七八九十0-9]+季|第[一二三四五六七八九十0-9]+部|\s*\d{4})$")


def norm_title(s):
    return SEASON.sub("", STOP.sub("", str(s)).lower())


def percentile(items):
    """数值热度→ln 分位(0-100)；无数值→榜位分位。"""
    if not items:
        return {}
    vals = sorted(math.log(it["heat"]) for it in items if it.get("heat"))
    res, n = {}, len(items)
    for pos, it in enumerate(items, 1):
        if it.get("heat") and vals:
            rk = sum(1 for v in vals if v <= math.log(it["heat"]))
            res[norm_title(it["title"])] = round(rk / len(vals) * 100, 1)
        else:
            res[norm_title(it["title"])] = round((n - pos + 1) / n * 100, 1)
    return res


WEIGHTS = {"tencent": 1.00, "iqiyi": 1.00, "youku": 0.90, "mgtv": 0.85, "bilibili": 0.75}


def unify(data):
    percents = {k: percentile(v) for k, v in data.items()}
    merged = {}
    for plat, pmap in percents.items():
        w = WEIGHTS[plat]
        for key, p in pmap.items():
            e = merged.setdefault(key, {"score": 0.0, "parts": {}})
            e["parts"][plat] = round(w * p, 1)
            e["score"] = max(e["score"], w * p)
    unified = []
    for key, e in merged.items():
        parts = sorted(e["parts"].values(), reverse=True)
        score = min(100.0, parts[0] + 0.12 * sum(parts[1:]))
        unified.append({"key": key, "score": round(score, 1), "parts": e["parts"]})
    unified.sort(key=lambda x: -x["score"])
    return unified


def main():
    print("采集五大平台真实热度…")
    data = {"tencent": fetch_tencent(), "iqiyi": fetch_iqiyi(), "youku": fetch_youku(),
            "mgtv": fetch_mgtv(), "bilibili": fetch_bilibili()}
    for k, v in data.items():
        print(f"  {k}: {len(v)} 条  top3: {[it['title'] for it in v[:3]]}")
    unified = unify(data)
    title_of = {}
    for items in data.values():
        for it in items:
            title_of.setdefault(norm_title(it["title"]), it["title"])
    board = [{"rank": i, "title": title_of.get(u["key"], u["key"]), "unified": u["score"],
              "platforms": u["parts"]} for i, u in enumerate(unified[:50], 1)]
    # real: 标题→真实热度索引（应用端按标题匹配用）
    real = {}
    for plat, items in data.items():
        for it in items:
            key = norm_title(it["title"])
            if not key:
                continue
            e = real.setdefault(key, {"title": it["title"], "p": {}})
            if it.get("heat"):
                e["p"][plat] = max(int(it["heat"]), e["p"].get(plat, 0))
    for u in unified:
        if u["key"] in real:
            real[u["key"]]["u"] = u["score"]
    heat = {"updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "algorithm": "per-platform ln-percentile/rank-percentile + weights + max+0.12*rest",
            "weights": WEIGHTS, "platforms": data, "unified": board, "real": real}
    with open((sys.argv[1] if len(sys.argv) > 1 else r"D:\xunidingweiceshi\tx_heat\heat.json"),
              "w", encoding="utf-8") as f:
        json.dump(heat, f, ensure_ascii=False, separators=(",", ":"))
    print("\n=== 综合真实热度榜 Top 15 ===")
    for b in board[:15]:
        ps = ",".join(f"{k}:{v}" for k, v in sorted(b["platforms"].items(), key=lambda x: -x[1]))
        print(f"  {b['rank']:>2}. {b['title'][:24]:<24} 综合{b['unified']:>5}  ({ps})")
    print(f"\nheat.json 已生成 ({len(board)} 条)")


if __name__ == "__main__":
    main()
