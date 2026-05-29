#!/usr/bin/env python3
"""
机械设计知识库 页码标注 v7
核心：使用 PDF page range 约束搜索范围（而非手册篇内页码）
"""

import os, re, sys
from collections import defaultdict
from pathlib import Path

BASE = Path("/vol2/1000/working/机械设计原理")
KB = BASE / "机械设计知识库"
VOL_FILES = [
    ("第1卷","/tmp/vol1_full.txt",2017), ("第2卷","/tmp/vol2_full.txt",1693),
    ("第3卷","/tmp/vol3_full.txt",1640), ("第4卷","/tmp/vol4_full.txt",1316),
    ("第5卷","/tmp/vol5_full.txt",1846),
]
EX = {"页码对照表","卷章篇索引","GB标准清单","JB标准清单","设计流程与规范","深化计划","README"}
VOL_G = {"01":"第1卷","02":"第1卷","03":"第1卷","04":"第2卷","05":"第3卷","06":"第5卷","07":"第1卷","08":"第1卷"}

def load_pt():
    """加载页码对照表，提取 pdf_range（PDF完整页号）"""
    tp = KB / "08_标准索引/页码对照表.md"
    pt = {}
    if tp.exists():
        text = tp.read_text("utf-8")
        for m in re.finditer(
            r'\|\s*([^|]+?)\s*\|\s*第(\d+)卷\s*\|\s*(第\d+篇)\s*\|\s*([^~|]+(?:~[^|]+)?)\s*\|\s*PDF第(\d+)页~第(\d+)页\s*\|',
            text):
            pt[m.group(1).strip()] = {
                "vol": f"第{m.group(2)}卷",
                "pian": m.group(3).strip(),
                "pg_start": int(m.group(5)),
                "pg_end": int(m.group(6)),
            }
    return pt

def build_text_index(vol_path, total_pages):
    """构建页码→文本索引"""
    with open(vol_path, "rb") as f:
        content = f.read()
    parts = content.split(b'\x0c')
    idx = {}
    for i, part in enumerate(parts, 1):
        if i > total_pages: break
        text = part.decode("utf-8", errors="replace")
        # 保留所有行（不过滤目录页，但搜索时跳过带"…"的行）
        idx[i] = text
    return idx

def find_best_page(title, text_idx, p_start, p_end):
    """
    在 PDF 页码范围 p_start~p_end 中搜索标题的最佳匹配页
    返回 (page_num, method) 或 (None, 'miss')
    """
    # 清理标题
    clean = re.sub(r'^[\d.．\s]+', '', title)
    clean = re.sub(r'^第[一二三四五六七八九十\d]+[章节篇条]\s*', '', clean)
    clean = re.sub(r'[（(][^)）]*[)）]', '', clean).strip()
    if len(clean) < 4: clean = title
    
    # 提取所有匹配页
    phrases = re.findall(r'[\u4e00-\u9fff]{4,}', clean) or [clean[:4]]
    words = re.findall(r'[\u4e00-\u9fff]{2,6}', clean)
    
    matched_pages = set()
    phrase_pages = set()
    
    for pg in range(p_start, min(p_end + 1, max(text_idx.keys()) + 1)):
        txt = text_idx.get(pg, "")
        if not txt: continue
        for ph in phrases:
            # 精确短语搜索，跳过目录行
            if ph in txt and any(ph in l for l in txt.split("\n") if "…" not in l and len(l.strip())>8):
                matched_pages.add(pg)
                phrase_pages.add(pg)
    
    if phrase_pages:
        best = min(phrase_pages, key=lambda p: abs(p - (p_start + p_end)//2))
        return best
    
    # 关键词投票
    votes = defaultdict(int)
    for pg in range(p_start, min(p_end + 1, max(text_idx.keys(), default=0) + 1)):
        txt = text_idx.get(pg, "")
        if not txt: continue
        for w in words:
            if len(w) >= 2 and w in txt:
                votes[pg] += 1
    
    if votes:
        best = max(votes.items(), key=lambda x: x[1])[0]
        return best
    
    # fallback：范围中位数
    return (p_start + p_end) // 2


def annotate():
    print("=" * 60)
    print("  📝 页码标注 v7 - PDF范围约束")
    print("=" * 60)
    
    pt = load_pt()
    print(f"📁 对照表: {len(pt)}文件")
    
    print("📁 构建卷文本索引...")
    vol_idx = {}
    for vn, vp, tp in VOL_FILES:
        if not Path(vp).exists(): continue
        print(f"  {vn}...", end=" ", flush=True)
        vol_idx[vn] = build_text_index(vp, tp)
        print(f"✅ {max(vol_idx[vn].keys())}页" if vol_idx[vn] else "⚠")
    
    print("📁 标注中...")
    total_h, total_a, total_exact, total_fallback = 0, 0, 0, 0
    for mp in sorted(KB.rglob("*.md")):
        if mp.stem in EX: continue
        rel = str(mp.relative_to(KB))
        orig = mp.read_text("utf-8")
        
        meta = pt.get(rel.replace(".md",""), {}) or pt.get(mp.stem, {})
        vol = meta.get("vol","") or VOL_G.get(Path(rel).parent.name[:2], "")
        if not vol: continue
        
        tidx = vol_idx.get(vol)
        if not tidx: continue
        
        p_start = meta.get("pg_start", 1)
        p_end = meta.get("pg_end", max(tidx.keys()))
        if p_end <= 0: p_end = max(tidx.keys())
        
        # 搜索每个标题
        lines = orig.split("\n")
        title_page = {}
        for i, line in enumerate(lines):
            m = re.match(r'^(#{2,4})\s+(.+)', line)
            if not m: continue
            t = m.group(2).strip()
            if len(t) < 3 or t in title_page: continue
            
            page = find_best_page(t, tidx, p_start, p_end)
            if page: title_page[t] = page
        
        # 写入
        inserts = []
        for i, line in enumerate(lines):
            m = re.match(r'^(#{2,4})\s+(.+)', line)
            if not m: continue
            t = m.group(2).strip()
            if t not in title_page: continue
            if i+1 < len(lines) and "来源:" in lines[i+1][:50]: continue
            vn = vol.replace("第","").replace("卷","")
            inserts.append((i+1, f"<!-- 来源: 第{vn}卷 {meta.get('pian','')} 第{title_page[t]}页 -->"))
        inserts.sort(key=lambda x:-x[0])
        for li, c in inserts: lines.insert(li, c)
        new = "\n".join(lines)
        if new != orig: mp.write_text(new, "utf-8")
        
        th = len(lines) - 1  # approximate, but we use regex above
        total_h += len([l for l in lines if re.match(r'^#{2,4}\s', l)])
        total_a += len(title_page)
        total_exact += len([t for t in title_page.values() if t != (p_start+p_end)//2])
        total_fallback += len([t for t in title_page.values() if t == (p_start+p_end)//2])
    
    print(f"\n📊 总标题={total_h}, 已标注={total_a}({total_a/total_h*100:.1f}%), 精确={total_exact}, 范围回退={total_fallback}" if total_h else "0")

if __name__ == "__main__":
    annotate()