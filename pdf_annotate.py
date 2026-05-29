#!/usr/bin/env python3
"""
PDF 精确页码提取 + 增强标注
用 PyMuPDF 读 PDF，提取每页高质量文本
替换 pdftotext 的低质量提取，提升标题匹配精度
"""
import json, os, re, sys
from collections import defaultdict
from pathlib import Path

BASE = Path("/vol2/1000/working/机械设计原理")
KB = BASE / "机械设计知识库"
PDFS = [
    ("第1卷", BASE / "机械设计手册 第六版 第1卷.PDF", 2017),
    ("第2卷", BASE / "机械设计手册 第六版 第2卷.PDF", 1693),
    ("第3卷", BASE / "-机械设计手册 第六版 第3卷.PDF", 1640),
    ("第4卷", BASE / "-机械设计手册 第六版 第4卷.PDF", 1316),
    ("第5卷", BASE / "-机械设计手册 第六版 第5卷.PDF", 1846),
]
EX = {"页码对照表","卷章篇索引","GB标准清单","JB标准清单","设计流程与规范","深化计划","README"}
VOL_G = {"01":"第1卷","02":"第1卷","03":"第1卷","04":"第2卷","05":"第3卷","06":"第5卷","07":"第1卷","08":"第1卷"}

PDF_INDEX_PATH = BASE / "机械设计知识库" / ".pdf_page_index.json"


def extract_pdf_pages(vol_name, pdf_path, expected_pages):
    """用 PyMuPDF 逐页提取文本"""
    import fitz
    print(f"  {vol_name}...", end=" ", flush=True)
    doc = fitz.open(str(pdf_path))
    pages = {}
    for i in range(min(doc.page_count, expected_pages)):
        text = doc[i].get_text("text")
        # 清理：压缩空白、移除孤立字符
        text = re.sub(r'\s+', ' ', text).strip()
        pages[i + 1] = text
    doc.close()
    print(f"✅ {len(pages)}页")
    return pages


def build_pdf_index():
    """提取所有卷的PDF页码内容"""
    print("=" * 60)
    print("  📄 读取PDF页码内容 (PyMuPDF)")
    print("=" * 60)
    
    idx = {}
    for vn, vp, ep in PDFS:
        if not vp.exists():
            print(f"  ⚠ {vp.name} 不存在")
            continue
        idx[vn] = extract_pdf_pages(vn, vp, ep)
    
    # 保存
    PDF_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    PDF_INDEX_PATH.write_text(json.dumps(idx, ensure_ascii=False), "utf-8")
    print(f"✅ 已保存到 {PDF_INDEX_PATH}")
    return idx


def search_in_pdf(pdf_pages, title, p_start, p_end):
    """
    在PDF页码范围中搜索标题，返回最佳页码
    PyMuPDF 文本质量更好，匹配率应该更高
    """
    clean = re.sub(r'^[\d.．\s]+', '', title)
    clean = re.sub(r'^第[一二三四五六七八九十\d]+[章节篇条]\s*', '', clean)
    clean = re.sub(r'[（(][^)）]*[)）]', '', clean).strip()
    if len(clean) < 4: clean = title
    
    phrases = re.findall(r'[\u4e00-\u9fff]{4,}', clean)
    words = re.findall(r'[\u4e00-\u9fff]{2,6}', clean)
    
    if not phrases: phrases = [clean[:4]]
    
    matched = {}
    for pg in range(p_start, min(p_end + 1, len(pdf_pages) + 1)):
        text = pdf_pages.get(pg, "")
        if not text: continue
        for ph in phrases:
            if ph in text:
                matched[pg] = matched.get(pg, 0) + 1
    
    if matched:
        mid = (p_start + p_end) // 2
        return min(matched, key=lambda p: abs(p - mid))
    
    # 关键词投票
    votes = defaultdict(int)
    for pg in range(p_start, min(p_end + 1, len(pdf_pages) + 1)):
        text = pdf_pages.get(pg, "")
        if not text: continue
        for w in words:
            if w in text:
                votes[pg] += 1
    if votes:
        return max(votes, key=lambda k: votes[k])
    
    return None


def reannotate_with_pdf():
    """用 PDF 提取的文本重新标注"""
    import fitz  # 确保能在导入时加载
    
    # 加载页码对照表
    tp = KB / "08_标准索引/页码对照表.md"
    pt = {}
    if tp.exists():
        for m in re.finditer(
            r'\|\s*([^|]+?)\s*\|\s*第(\d+)卷\s*\|\s*(第\d+篇)\s*\|\s*([^~|]+(?:~[^|]+)?)\s*\|\s*PDF第(\d+)页~第(\d+)页\s*\|',
            tp.read_text("utf-8")):
            pt[m.group(1).strip()] = {
                "vol": f"第{m.group(2)}卷", "pian": m.group(3).strip(),
                "pdf_start": int(m.group(5)), "pdf_end": int(m.group(6)),
            }
    print(f"📁 对照表: {len(pt)}文件")
    
    # 检查PDF索引是否存在
    if PDF_INDEX_PATH.exists():
        print("📁 加载已有PDF页码索引...")
        pdf_idx = json.loads(PDF_INDEX_PATH.read_text("utf-8"))
    else:
        print("📁 提取PDF页码内容...")
        pdf_idx = {}
        for vn, vp, ep in PDFS:
            if not vp.exists(): continue
            pages = extract_pdf_pages(vn, vp, ep)
            pdf_idx[vn] = pages
        PDF_INDEX_PATH.write_text(json.dumps(pdf_idx, ensure_ascii=False), "utf-8")
    
    # 标注
    print("📁 增强标注中...")
    total_h, total_a, total_exact, total_fallback = 0, 0, 0, 0
    stats = []
    
    for mp in sorted(KB.rglob("*.md")):
        if mp.stem in EX: continue
        rel = str(mp.relative_to(KB))
        orig = mp.read_text("utf-8")
        
        meta = pt.get(rel.replace(".md",""), {}) or pt.get(mp.stem, {})
        vol = meta.get("vol","") or VOL_G.get(Path(rel).parent.name[:2], "")
        if not vol: continue
        
        pdf_pages = pdf_idx.get(vol)
        if not pdf_pages: continue
        
        p_start = meta.get("pdf_start", 1)
        p_end = meta.get("pdf_end", max(pdf_pages.keys()))
        mid = (p_start + p_end) // 2
        
        lines = orig.split("\n")
        title_page = {}
        
        for i, line in enumerate(lines):
            m = re.match(r'^(#{2,4})\s+(.+)', line)
            if not m: continue
            t = m.group(2).strip()
            if len(t) < 3 or t in title_page: continue
            
            page = search_in_pdf(pdf_pages, t, p_start, p_end)
            if page:
                title_page[t] = page
            else:
                title_page[t] = mid
                total_fallback += 1
        
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
        
        h = len([l for l in lines if re.match(r'^#{2,4}\s', l)])
        a = len(title_page)
        exact = a - (1 if mid in title_page.values() else 0)
        total_h += h; total_a += a; total_exact += exact
        
        if a > 0:
            stats.append((rel, h, a, f"✅ {a}/{h} (回退{a - exact})"))
        else:
            stats.append((rel, h, 0, f"   0/{h}"))
    
    print()
    for _, _, _, s in stats: print(f"  {s}")
    af = sum(1 for _,_,a,_ in stats if a > 0)
    print(f"\n📊 {len(stats)}文件, {af}有标注, {total_h}标题→{total_a}({total_a/total_h*100:.1f}%), 范围回退={total_fallback}")


if __name__ == "__main__":
    reannotate_with_pdf()