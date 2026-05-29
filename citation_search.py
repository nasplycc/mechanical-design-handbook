#!/usr/bin/env python3
"""
机械设计手册 引用检索系统 v5 - 精确页码 + 嵌入注释
基于《机械设计手册》第六版 5卷8512页
策略：知识库搜索 + 嵌入页注 + 原文精确页码定位
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path("/vol2/1000/working/机械设计原理")
KB_DIR = BASE_DIR / "机械设计知识库"
PAGE_INDEX_PATH = KB_DIR / ".page_index.json"
KB_INDEX_PATH = BASE_DIR / ".kb_index.json"

VOL_FILES = [
    ("第1卷", "/tmp/vol1_full.txt", 2017),
    ("第2卷", "/tmp/vol2_full.txt", 1693),
    ("第3卷", "/tmp/vol3_full.txt", 1640),
    ("第4卷", "/tmp/vol4_full.txt", 1316),
    ("第5卷", "/tmp/vol5_full.txt", 1846),
]

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

# ══════════ 索引 ══════════

def build_page_index():
    """构建页码→字节偏移索引（基于\\f换页符）"""
    print("=" * 60)
    print("  📄 构建精确页码索引...")
    print("=" * 60)
    page_index = {}
    for vol_name, vol_path, total_pages in VOL_FILES:
        if not Path(vol_path).exists():
            continue
        print(f"  {vol_name}...", end=" ", flush=True)
        with open(vol_path, "rb") as f:
            content = f.read()
        offsets = []
        pos = 0
        while True:
            idx = content.find(b'\x0c', pos)
            if idx < 0:
                break
            offsets.append(idx)
            pos = idx + 1
        pages = []
        for i, off in enumerate(offsets):
            start = off + 1
            end = offsets[i+1] if i+1 < len(offsets) else len(content)
            pages.append({"page": i+1, "byte_start": start, "byte_end": end})
        page_index[vol_name] = {"path": vol_path, "total_pages": total_pages, "pages": pages}
        status = "✅" if len(pages) == total_pages else f"⚠ {len(pages)}/{total_pages}"
        print(status)
    PAGE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAGE_INDEX_PATH.write_text(json.dumps(page_index, ensure_ascii=False, indent=1), "utf-8")
    print(f"✅ 页码索引已保存")
    return page_index


def build_kb_index(cached=True):
    """构建/加载知识库索引"""
    if cached and KB_INDEX_PATH.exists():
        newest_md = max(f.stat().st_mtime for f in KB_DIR.rglob("*.md"))
        if os.path.getmtime(KB_INDEX_PATH) >= newest_md:
            raw = json.loads(KB_INDEX_PATH.read_text("utf-8"))
            print(f"📁 加载知识库索引 ({len(raw['file_info'])}文件)")
            return raw["file_info"], raw["keyword_index"]
    print("📁 构建知识库索引...")
    exclude = {"页码对照表","卷章篇索引","GB标准清单","JB标准清单",
               "设计流程与规范","深化计划","README"}
    table_path = KB_DIR / "08_标准索引/页码对照表.md"
    ptable = {}
    if table_path.exists():
        for m in re.finditer(r'\|\s*([^|]+?)\s*\|\s*第(\d+)卷\s*\|\s*(第\d+篇)\s*\|\s*([^~|]+(?:~[^|]+)?)\s*\|\s*([^|]+?)\s*\|',
                              table_path.read_text("utf-8")):
            ptable[m.group(1).strip()] = {"vol": f"第{m.group(2)}卷", "pian": m.group(3).strip()}
    file_info = {}
    kw_idx = defaultdict(list)
    for md_path in sorted(KB_DIR.rglob("*.md")):
        fname = md_path.stem
        if fname in exclude:
            continue
        rel = str(md_path.relative_to(KB_DIR))
        text = md_path.read_text("utf-8", errors="replace")
        meta = ptable.get(rel.replace(".md",""), {}) or ptable.get(fname, {})
        meta["path"] = rel
        if not meta.get("vol"):
            prefix = Path(rel).parent.name[:2]
            vmap = {"01":"第1卷","02":"第1卷","03":"第1卷","04":"第2卷",
                    "05":"第3卷","06":"第5卷","07":"第1卷","08":"第1卷"}
            meta["vol"] = vmap.get(prefix, "")
        file_info[rel] = meta
        for line in text.split("\n"):
            for w in set(re.findall(r'[\u4e00-\u9fff]{2,8}', line)):
                kw_idx[w].append((rel, line.strip()[:100]))
    KB_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    KB_INDEX_PATH.write_text(json.dumps({"file_info": file_info, "keyword_index": dict(kw_idx)},
                                         ensure_ascii=False, indent=1), "utf-8")
    print(f"📁 索引: {len(file_info)}文件, {len(kw_idx)}关键词")
    return file_info, kw_idx


# ══════════ 搜索 ══════════

def search_in_file(text, query):
    """在单个文件文本中搜索，返回(得分, 匹配行列表, 嵌入页注列表)"""
    score = 0
    lines = []
    # 生成多级别分词
    all_words = set()
    # 完整短语（4~6字）
    for w in re.findall(r'[\u4e00-\u9fff]{4,6}', query):
        all_words.add(w)
    # 2~3字短词
    for w in re.findall(r'[\u4e00-\u9fff]{2,3}', query):
        if len(w) >= 2:
            all_words.add(w)
    # 将词按长度排序
    words_by_len = sorted(all_words, key=len, reverse=True)
    
    if query[:4] in text:
        score += 40
    for w in words_by_len:
        cnt = text.count(w)
        if cnt:
            score += cnt * (5 if len(w) >= 4 else 2)
    
    for line in text.split("\n"):
        line_s = line.strip()
        if not line_s or line_s.startswith("<!--"):
            continue
        for w in words_by_len:
            if w in line_s:
                lines.append(line_s[:110])
                break
    
    # 提取嵌入的页码注释
    annotations = []
    for m in re.finditer(r'<!--\s*来源:\s*(第\d+卷)\s*(第\d+篇\s*[^第]*?)?\s*(第\d+页)\s*-->', text):
        vol = m.group(1)
        page = m.group(3)
        pian = m.group(2) or ""
        annotations.append({"vol": vol, "page": page, "pian": pian.strip()})
    
    # 去重行
    seen = set()
    deduped = []
    for l in lines:
        key = l[:50]
        if key not in seen:
            seen.add(key)
            deduped.append(l)
    
    return score, deduped[:10], annotations


def search(query, file_info, kw_idx):
    """多文件检索"""
    # 生成多级别关键词
    all_words = set()
    for w in re.findall(r'[\u4e00-\u9fff]{4,6}', query):
        all_words.add(w)
    for w in re.findall(r'[\u4e00-\u9fff]{2,3}', query):
        if len(w) >= 2:
            all_words.add(w)
    
    paths = set()
    for token in all_words:
        for kw, entries in kw_idx.items():
            if token in kw or kw in token:
                for path, _ in entries:
                    paths.add(path)
    results = []
    for path in paths:
        fp = KB_DIR / path
        if not fp.exists():
            continue
        text = fp.read_text("utf-8", errors="replace")
        score, lines, anns = search_in_file(text, query)
        if score > 0:
            meta = file_info.get(path, {})
            results.append({
                "path": path, "score": score, "lines": lines,
                "annotations": anns,
                "vol": meta.get("vol",""), "pian": meta.get("pian",""),
            })
    results.sort(key=lambda r: -r["score"])
    return results[:10]


# ══════════ 显示 ══════════

def display(results, query):
    print(f"\n📖 检索结果：{query}")
    print("=" * 60)
    if not results:
        print("  😕 未找到相关结果")
        return
    for i, r in enumerate(results[:6], 1):
        print(f"\n{'─' * 50}")
        print(f"  #{i}  {r['path']}  (得分: {r['score']})")
        if r['pian']:
            print(f"  📍 {r['vol']} {r['pian']} {PIAN_NAMES.get(r['pian'],'')}")
        elif r['vol']:
            print(f"  📍 {r['vol']}")
        if r['lines']:
            print(f"  ┌─ 知识库内容")
            for line in r['lines'][:4]:
                line = line.replace("　"," ").replace("  "," ").strip()
                if line: print(f"  │ {line[:110]}")
        if r['annotations']:
            print(f"  └─ 精确页码引用")
            seen_p = set()
            for a in r['annotations'][:6]:
                key = f"{a['vol']} {a['page']}"
                if key in seen_p:
                    continue
                seen_p.add(key)
                print(f"      📄 {a['vol']} {a['pian']} {a['page']}")
        if len(seen_p) >= 3:
            break


def interactive():
    print("=" * 60)
    print("  📚 机械设计手册 引用检索系统")
    print("  输入查询 / exit 退出")
    print("=" * 60)
    fi, ki = build_kb_index()
    while True:
        try:
            q = input("\n🔍 ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q.lower() in ("exit","quit"):
            break
        results = search(q, fi, ki)
        display(results, q)


# ══════════ CLI ══════════

def main():
    parser = argparse.ArgumentParser(description="机械设计手册 引用检索系统 v5")
    parser.add_argument("--build-index", action="store_true")
    parser.add_argument("--query", type=str)
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    
    if args.build_index:
        build_page_index()
        build_kb_index(False)
        print("\n✅ 所有索引构建完成")
        return
    
    fi, ki = build_kb_index()
    
    if args.query:
        results = search(args.query, fi, ki)
        display(results, args.query)
    elif args.interactive:
        interactive()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()