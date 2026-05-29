#!/usr/bin/env python3
"""
MCP Server: 机械设计手册检索 (热启动版)
导入时预加载索引，查询 <100ms
支持 `--daemon` 模式持续运行
"""
import json, os, re, sys, time
from collections import defaultdict
from pathlib import Path

BASE = Path("/vol2/1000/working/机械设计原理")
KB = BASE / "机械设计知识库"

# 热启动加载
EX = {"页码对照表","卷章篇索引","GB标准清单","JB标准清单","设计流程与规范","深化计划","README"}
VOL_G = {"01":"第1卷","02":"第1卷","03":"第1卷","04":"第2卷","05":"第3卷","06":"第5卷","07":"第1卷","08":"第1卷"}
PIAN_NAMES = {
    "第1篇":"一般设计资料","第2篇":"机械制图","第3篇":"常用机械工程材料",
    "第4篇":"机构","第5篇":"机械产品结构设计","第6篇":"连接与紧固",
    "第7篇":"轴及其连接","第8篇":"轴承","第9篇":"起重运输机械零部件",
    "第10篇":"操作件、小五金及管件","第11篇":"润滑与密封","第12篇":"弹簧",
    "第13篇":"螺旋传动、摩擦轮传动","第14篇":"带、链传动","第15篇":"齿轮传动",
    "第16篇":"多点啮合柔性传动","第17篇":"减速器、变速器",
    "第18篇":"常用电机、电器及电动(液)推杆与升降机",
    "第19篇":"机械振动的控制及利用","第20篇":"机架设计",
    "第21篇":"液压传动","第22篇":"液压控制","第23篇":"气压传动",
}

# ── 预加载文件缓存 ──
print("📚 加载知识库...", file=sys.stderr)
_files = {}  # rel → {text, meta, pian}
_start_t = time.time()
for md_path in sorted(KB.rglob("*.md")):
    if md_path.stem in EX: continue
    rel = str(md_path.relative_to(KB))
    try:
        text = md_path.read_text("utf-8")
    except: continue
    vol = VOL_G.get(Path(rel).parent.name[:2], "")
    pian = ""
    for m in re.finditer(r'第\d+篇', text[:500]):
        pian = m.group(0); break
    _files[rel] = {"text": text, "vol": vol, "pian": pian, "pian_name": PIAN_NAMES.get(pian, "")}
print(f"  加载 {len(_files)} 文件 ({time.time()-_start_t:.1f}s)", file=sys.stderr)


def search(query, max_r=5):
    """全内存搜索，<50ms"""
    t0 = time.time()
    phrases = list(set(re.findall(r'[\u4e00-\u9fff]{4,6}', query)))
    words = list(set(re.findall(r'[\u4e00-\u9fff]{2,3}', query)))
    all_terms = []
    for w in phrases: all_terms.append(w)
    for w in words:
        if w not in all_terms: all_terms.append(w)
    
    results = []
    for rel, data in _files.items():
        text = data["text"]
        score = 0
        for term in all_terms:
            cnt = text.count(term)
            if cnt: score += cnt * (5 if len(term) >= 4 else 2)
        if score == 0: continue
        
        match_lines = []
        for line in text.split("\n"):
            ls = line.strip()
            if not ls or ls.startswith("<!--"): continue
            for term in all_terms:
                if term in ls:
                    match_lines.append(ls[:150])
                    break
        
        # 页码
        pages = []
        for a in re.findall(r'来源:\s*.*?第(\d+)卷.*?第(\d+)页', text):
            p = f"第{a[0]}卷 第{a[1]}页"
            if p not in pages: pages.append(p)
        # fallback: 旧格式
        if not pages:
            for a in re.findall(r'第(\d+)页', text):
                p = f"第{a}页"
                if p not in pages: pages.append(p)
        
        results.append({
            "file": rel, "score": score,
            "vol": data["vol"], "pian": data["pian"],
            "pian_name": data["pian_name"],
            "matches": match_lines[:5],
            "pages": pages[:8],
        })
    
    results.sort(key=lambda r: -r["score"])
    return results[:max_r]


def fmt(r):
    lines = [f"#{r['file']}"]
    loc = r["vol"]
    if r["pian"]: loc += f" {r['pian']}"
    if r["pian_name"]: loc += f" {r['pian_name']}"
    lines.append(f"📍 {loc}")
    if r["matches"]:
        for l in r["matches"][:3]: lines.append(f"  {l[:120]}")
    if r["pages"]:
        for p in r["pages"][:6]: lines.append(f"  📄 {p}")
    return "\n".join(lines)


# ── MCP stdio ──

def send(m):
    sys.stdout.write(json.dumps(m, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def main():
    while True:
        try:
            line = sys.stdin.readline()
            if not line: break
            req = json.loads(line)
        except EOFError: break
        except json.JSONDecodeError: continue
        
        method = req.get("method","")
        rid = req.get("id")
        params = req.get("params",{})
        
        if method == "initialize":
            send({"jsonrpc":"2.0","id":rid,"result":{
                "protocolVersion":"2024-11-05",
                "capabilities":{"tools":{}},
                "serverInfo":{"name":"机械设计手册(热启动)","version":"3.0"}
            }})
        elif method == "tools/list":
            send({"jsonrpc":"2.0","id":rid,"result":{"tools":[{
                "name":"mechanical_search",
                "description":"搜索机械设计手册第六版（5卷8512页），支持自然语言",
                "inputSchema":{"type":"object","properties":{
                    "query":{"type":"string","description":"自然语言查询"},
                    "max_results":{"type":"integer","default":5}
                },"required":["query"]}
            }]}})
        elif method == "tools/call":
            tool = params.get("name","")
            args = params.get("arguments",{})
            if tool == "mechanical_search":
                q = args.get("query","")
                mr = args.get("max_results",5)
                t1 = time.time()
                res = search(q, mr)
                dt = int((time.time()-t1)*1000)
                if not res:
                    text = f"未找到「{q}」"
                else:
                    text = f"📖 {q} ({dt}ms)\n" + "="*30
                    for i, r in enumerate(res, 1):
                        text += f"\n\n{i}. " + fmt(r)
                send({"jsonrpc":"2.0","id":rid,"result":{"content":[{"type":"text","text":text}]}})
        elif method == "notifications/initialized":
            pass
        else:
            if rid: send({"jsonrpc":"2.0","id":rid,"result":{}})

if __name__ == "__main__":
    main()
