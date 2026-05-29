#!/usr/bin/env python3
"""
机械设计手册 检索系统 v6 - 增强版
支持自然语言查询拆解，可直接调用 (CLI) 或作为 MCP server

用法:
  python3 search.py "齿轮齿条运动机构"
  python3 search.py -i                     # 交互模式
"""
import json, os, re, sys
from collections import defaultdict
from pathlib import Path

# BM25 语义搜索兜底
_BM25 = None
def _ensure_bm25():
    global _BM25
    if _BM25 is not None:
        return _BM25
    t0 = __import__('time').time()
    from bm25_search import BM25Search
    bm = BM25Search(cache_path=str(BASE / '.bm25_index.json'))
    if not bm.load_cache():
        # 构建索引
        docs = []
        KB2 = Path(str(KB))
        EX2 = {"页码对照表","卷章篇索引","GB标准清单","JB标准清单","设计流程与规范","深化计划","README",".gitignore"}
        for p in sorted(KB2.rglob("*.md")):
            if p.stem in EX2: continue
            try:
                t = p.read_text("utf-8")
            except: continue
            rel = str(p.relative_to(KB2))
            docs.append({"id": rel, "text": re.sub(r'<!--.*?-->', '', t)})
        bm.fit(docs)
    _BM25 = bm
    return bm

BASE = Path("/vol2/1000/working/机械设计原理")
KB = BASE / "机械设计知识库"
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

# ── 知识图谱：设计问题→关键词映射 ──
DOMAIN_KEYWORDS = {
    "传动": ["齿轮传动","带传动","链传动","蜗杆传动","螺旋传动","摩擦轮","减速器","变速器"],
    "齿轮": ["齿轮","齿条","齿轮齿条","斜齿轮","锥齿轮","蜗杆","模数","渐开线","变位齿轮"],
    "带": ["V带","同步带","平带","带传动","带轮","张紧力","包角"],
    "链": ["滚子链","齿形链","链轮","链条","链传动"],
    "轴承": ["深沟球","角接触","圆锥滚子","调心滚子","推力球","轴承寿命","轴承选型","滚动轴承"],
    "轴": ["转轴","心轴","传动轴","联轴器","离合器","轴系","花键"],
    "弹簧": ["压缩弹簧","拉伸弹簧","扭转弹簧","碟形弹簧","板弹簧","弹簧设计"],
    "螺纹": ["螺纹连接","螺栓","螺钉","螺母","垫圈","螺距","紧固件"],
    "键": ["平键","半圆键","花键","导向键","键连接"],
    "液压": ["液压泵","液压缸","液压马达","溢流阀","换向阀","液压回路","液压系统"],
    "气压": ["气缸","气动马达","空压机","气动阀","气压回路"],
    "材料": ["钢材","铸铁","铝合金","铜合金","工程塑料","热处理","调质","渗碳","淬火","正火"],
    "润滑": ["润滑油","润滑脂","油浴","浸油","密封","O形圈","机械密封"],
    "电机": ["电动机","伺服电机","步进电机","减速电机"],
    "振动": ["隔振","减振","临界转速","动平衡","噪声控制"],
    "机架": ["机架","焊接机架","床身","导轨","筋板"],
    "结构": ["结构设计","铸造","锻造","冲压","焊接","机加工"],
    "公差": ["公差","配合","IT等级","粗糙度","形位公差"],
    "减速器": ["减速器","变速器","齿轮箱","行星齿轮","谐波减速器"],
    "焊接": ["焊接","焊缝","焊条","焊接结构","焊接接头"],
}

# ── 工具函数 ──

def parse_query(nl_query):
    """
    自然语言→技术关键词
    先查知识图谱映射，再逐字拆词
    """
    query_lower = nl_query.lower()
    keywords = set()
    
    # 1. 知识图谱匹配
    for domain, terms in DOMAIN_KEYWORDS.items():
        domain_words = re.findall(r'[\u4e00-\u9fff]+', domain)
        for dw in domain_words:
            if dw in nl_query:
                for t in terms:
                    keywords.add(t)
        for term in terms:
            if term in nl_query:
                keywords.add(term)
    
    # 2. 直接提取中文词
    # 短语（4-6字）
    for w in re.findall(r'[\u4e00-\u9fff]{4,6}', nl_query):
        keywords.add(w)
    # 短词（2-3字）
    for w in re.findall(r'[\u4e00-\u9fff]{2,3}', nl_query):
        if len(w) >= 2:
            keywords.add(w)
    
    return list(keywords)


def search_kb(keywords, max_results=5):
    """搜索知识库（关键词 + BM25 语义兜底）"""
    # 扫描所有文件
    results = []
    for md_path in KB.rglob("*.md"):
        if md_path.stem in EX: continue
        try:
            text = md_path.read_text("utf-8", errors="replace")
        except: continue
        
        score = 0
        match_lines = []
        annotations = []
        
        for kw in keywords:
            cnt = text.count(kw)
            if cnt:
                score += cnt * (5 if len(kw) >= 4 else 2)
        
        if score == 0: continue
        
        for line in text.split("\n"):
            ls = line.strip()
            if not ls: continue
            if ls.startswith("<!--") and "来源" in ls:
                annotations.append(ls)
            for kw in keywords:
                if kw in ls and not ls.startswith("<!--"):
                    if ls[:100] not in [l[:100] for l in match_lines]:
                        match_lines.append(ls[:150])
                    break
        
        rel = str(md_path.relative_to(KB))
        vol = VOL_G.get(Path(rel).parent.name[:2], "")
        pian = ""
        for m in re.finditer(r'第\d+篇', text[:500]):
            pian = m.group(0); break
        
        pages = []
        for a in annotations:
            m = re.search(r'第(\d+)页', a)
            pian_m = re.search(r'第(\d+)篇', a)
            vol_m = re.search(r'第(\d+)卷', a)
            if m and pian_m and vol_m:
                p = f"第{vol_m.group(1)}卷 第{pian_m.group(1)}篇 第{m.group(1)}页"
                if p not in pages: pages.append(p)
        
        results.append({
            "file": rel, "score": score,
            "vol": vol, "pian": pian,
            "pian_name": PIAN_NAMES.get(pian, ""),
            "matches": match_lines[:5],
            "pages": pages[:8],
        })
    
    results.sort(key=lambda r: -r["score"])
    
    # BM25 语义兜底：关键词无结果 / 少于2条 / 最高分太低(<=50) 时触发
    top_score = results[0]["score"] if results else 0
    if (len(results) < 2 or top_score <= 50) and keywords:
        try:
            bm = _ensure_bm25()
            query_str = " ".join(keywords)
            bm_results = bm.search(query_str, top_k=max_results)
            if bm_results:
                # 合并，避免关键词结果被覆盖
                bm_ids = {d["id"] for d in bm_results}
                kw_ids = {r["file"] for r in results}
                for bd in bm_results:
                    if bd["id"] not in kw_ids:
                        # 读取文件获取详细信息
                        fp = KB / bd["id"]
                        if fp.exists():
                            t = fp.read_text("utf-8", errors="replace")
                            rel = bd["id"]
                            vol = VOL_G.get(Path(rel).parent.name[:2], "")
                            pian = ""
                            for m in re.finditer(r'第\d+篇', t[:500]):
                                pian = m.group(0); break
                            annotations = [l for l in t.split("\n") if l.strip().startswith("<!--") and "来源" in l]
                            pages = []
                            for a in annotations:
                                m = re.search(r'第(\d+)页', a)
                                vm = re.search(r'第(\d+)卷', a)
                                if m and vm:
                                    p = f"第{vm.group(1)}卷 第{m.group(1)}页"
                                    if p not in pages: pages.append(p)
                            results.append({
                                "file": rel,
                                "score": round(bd.get("bm25_score", 0) * 100),
                                "vol": vol, "pian": pian,
                                "pian_name": PIAN_NAMES.get(pian, ""),
                                "matches": [f"[BM25 语义匹配] {bd.get('bm25_score', 0):.3f}"],
                                "pages": pages[:8],
                            })
                results.sort(key=lambda r: -r["score"])
        except Exception as e:
            pass  # BM25 可用
    
    return results[:max_results]


def format_search_results(results, query, max_r=5, telegram=False):
    """格式化搜索结果
    telegram=True 时精简输出 + 生成网页链接
    """
    if not results:
        return f"未找到与「{query}」相关的设计资料"
    
    if telegram:
        # Telegram 精简版
        lines = [f"📖 {query}", ""]
        for i, r in enumerate(results[:max_r], 1):
            loc = f"{r['vol']} {r['pian']}" if r['pian'] else r['vol']
            if r['pian_name'] and not r['pian'] in loc:
                loc += f" {r['pian_name']}"
            lines.append(f"{i}. {r['file']}")
            lines.append(f"   📍 {loc}")
            # 只显示页码链接或简短匹配
            pages_shown = r['pages'][:3]
            if pages_shown:
                page_links = []
                for p in pages_shown:
                    m = re.search(r'第(\d+)卷.*?第(\d+)页', p)
                    if m:
                        page_links.append(f"/pdf/{m.group(1)}#page={m.group(2)}")
                    else:
                        page_links.append(p)
                if page_links:
                    lines.append(f"   📄 {' | '.join(page_links)}")
            if r['matches']:
                # 简短摘要
                summary = r['matches'][0][:80]
                lines.append(f"   {summary}")
            lines.append("")
        
        lines.append(f"🌐 http://localhost:5231  → Web 查看完整内容")
        lines.append(f"💡 共 {len(results)} 个文件相关")
        return "\n".join(lines)
    
    # 终端完整版
    parts = [f"📖 搜索设计资料：{query}", "=" * 40]
    
    for i, r in enumerate(results, 1):
        parts.append(f"\n{'─' * 40}")
        parts.append(f"#{i} {r['file']}")
        loc = f"{r['vol']} {r['pian']}" if r['pian'] else r['vol']
        if r['pian_name']:
            loc += f" {r['pian_name']}"
        parts.append(f"📍 {loc}")
        
        if r['matches']:
            parts.append("📋 关键内容：")
            for ln in r['matches'][:3]:
                parts.append(f"   {ln[:120]}")
        
        if r['pages']:
            parts.append("📄 精确页码：")
            seen = set()
            for p in r['pages']:
                if p not in seen:
                    seen.add(p)
                    parts.append(f"   {p}")
    
    if len(results) >= 5:
        parts.append(f"\n💡 找到 {len(results)} 个相关文件，建议细化关键词获取更精确结果。")
    
    return "\n".join(parts)


# ── CLI 入口 ──

def cli():
    query = " ".join(sys.argv[1:])
    if not query or query == "-i":
        # 交互模式
        print("🔍 机械设计手册查询 (输入 exit 退出)")
        while True:
            try:
                q = input("\n查询 > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q or q.lower() in ("exit","quit"): break
            kws = parse_query(q)
            results = search_kb(kws)
            print(format_search_results(results, q))
        return
    
    kws = parse_query(query)
    results = search_kb(kws)
    print(format_search_results(results, query))


if __name__ == "__main__":
    cli()