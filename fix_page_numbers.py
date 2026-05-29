#!/usr/bin/env python3
"""
重建全部页码标注 — 从 PDF 提取精确印刷页码 (篇-页号)

用法: python3 fix_page_numbers.py
"""
import fitz, re, json, time
from pathlib import Path

BASE = Path("/vol2/1000/working/机械设计原理")
KB = BASE / "机械设计知识库"
EX = {"页码对照表","卷章篇索引","GB标准清单","JB标准清单","设计流程与规范","深化计划","README",".gitignore"}

VOL_PDFS = {
    "1": BASE / "机械设计手册 第六版 第1卷.PDF",
    "2": BASE / "机械设计手册 第六版 第2卷.PDF",
    "3": BASE / "-机械设计手册 第六版 第3卷.PDF",
    "4": BASE / "-机械设计手册 第六版 第4卷.PDF",
    "5": BASE / "-机械设计手册 第六版 第5卷.PDF",
}

PIAN_NAMES_SHORT = {
    1:"一般设计资料",2:"机械制图",3:"常用机械工程材料",4:"机构",5:"机械产品结构设计",
    6:"连接与紧固",7:"轴及其连接",8:"轴承",9:"起重运输机械零部件",10:"操作件、小五金及管件",
    11:"润滑与密封",12:"弹簧",13:"螺旋传动、摩擦轮传动",14:"带、链传动",15:"齿轮传动",
    16:"多点啮合柔性传动",17:"减速器、变速器",18:"常用电机、电器及电动(液)推杆与升降机",
    19:"机械振动的控制及利用",20:"机架设计",21:"液压传动",22:"液压控制",23:"气压传动",
}
PIAN_VOL = {"第1篇":"第1卷","第2篇":"第1卷","第3篇":"第1卷","第4篇":"第1卷","第5篇":"第1卷",
    "第6篇":"第2卷","第7篇":"第2卷","第8篇":"第2卷","第9篇":"第2卷","第10篇":"第2卷",
    "第11篇":"第3卷","第12篇":"第3卷","第13篇":"第3卷","第14篇":"第3卷","第15篇":"第3卷",
    "第16篇":"第3卷","第17篇":"第4卷","第18篇":"第5卷","第19篇":"第5卷","第20篇":"第4卷",
    "第21篇":"第4卷","第22篇":"第4卷","第23篇":"第5卷",}

def fullwidth_to_int(s):
    """全角数字→整数"""
    try: return int(s)
    except:
        try: return int(''.join(str('０１２３４５６７８９'.index(c)) for c in s if c in '０１２３４５６７８９'))
        except: return None

def extract_pian_mapping(vol_num, pdf_path):
    """从PDF提取 (PDF页号→印刷页号) 映射"""
    print(f"  第{vol_num}卷: 读取中...")
    doc = fitz.open(str(pdf_path))
    total = doc.page_count
    mapping = {}
    
    for i in range(total):
        page = doc[i]
        text = page.get_text('text')
        lines = text.split('\n')
        
        # 在前10行和后10行中搜索印刷页码标记
        found = None
        for l in lines[:12] + lines[-12:]:
            l = l.strip()
            # 匹配 篇号⁃页号 格式 (全角篇号 + 短横 + 半角数字)
            m = re.match(r'^([１２３４５６７８９０]{1,2})[⁃\-](\d+)$', l)
            if m:
                pian = fullwidth_to_int(m.group(1))
                if pian and 1 <= pian <= 23:
                    printed_pn = int(m.group(2))
                    if 1 <= printed_pn <= 1500:
                        found = (pian, printed_pn)
                        break
        
        if found:
            mapping[i+1] = found  # PDF第(i+1)页 → (篇号, 篇内页号)
    
    doc.close()
    print(f"    提取了 {len(mapping)} 页印刷页码 (共{total}页)")
    return mapping

def build_all_mappings():
    """构建所有卷的映射"""
    all_mappings = {}
    for vol_num in ["1","2","3","4","5"]:
        pdf = VOL_PDFS[vol_num]
        if not pdf.exists():
            print(f"  ⚠️ 第{vol_num}卷PDF不存在: {pdf}")
            continue
        m = extract_pian_mapping(vol_num, pdf)
        all_mappings[vol_num] = m
        # 保存缓存
        cache_path = BASE / f".pian_map_v{vol_num}.json"
        with open(cache_path, "w") as f:
            json.dump(m, f)
    return all_mappings

def load_or_build_mappings():
    """优先加载缓存"""
    cache_files = [BASE / f".pian_map_v{v}.json" for v in ["1","2","3","4","5"]]
    all_cached = all(cf.exists() for cf in cache_files)
    
    if all_cached:
        print("📦 加载缓存的印刷页码索引...")
        all_mappings = {}
        for vol_num in ["1","2","3","4","5"]:
            with open(BASE / f".pian_map_v{vol_num}.json") as f:
                # JSON keys are strings, convert back to int
                raw = json.load(f)
                all_mappings[vol_num] = {int(k): v for k, v in raw.items()}
        return all_mappings
    else:
        print("🔍 从PDF提取印刷页码索引...")
        return build_all_mappings()

def fix_annotation(mappings, vol_num, pdf_page):
    """转换PDF页→印刷页"""
    m = mappings.get(vol_num, {})
    pdf_pn = int(pdf_page)
    if pdf_pn in m:
        pian, printed_pn = m[pdf_pn]
        return pian, printed_pn
    # 找最近的
    if m:
        nearest = min(m.keys(), key=lambda k: abs(k - pdf_pn))
        return m[nearest][0], m[nearest][1]
    return None, None

def main():
    t0 = time.time()
    mappings = load_or_build_mappings()
    print(f"⏱ 索引加载: {(time.time()-t0)*1000:.0f}ms\n")
    
    # 统计算法
    total_annotations = 0
    fixed_annotations = 0
    range_fallbacks = 0
    deleted_front_matter = 0
    file_changes = {}
    
    for p in sorted(KB.rglob("*.md")):
        if p.stem in EX: continue
        text = p.read_text("utf-8")
        new_text = text
        changed = False
        annotations = re.findall(r'<!-- 来源:.*?第(\d+)卷.*?第(\d+)页', text)
        
        for vol_num, pdf_page in annotations:
            total_annotations += 1
            pian, printed_pn = fix_annotation(mappings, vol_num, pdf_page)
            
            if pian and printed_pn:
                old = f"第{vol_num}卷  第{pdf_page}页"
                # 跳过前言/目录页
                if printed_pn <= 2 or (pian == 1 and printed_pn <= 10):
                    new_text = new_text.replace(old, f"第{pian}篇 第{printed_pn}页 [前言]")
                    deleted_front_matter += 1
                else:
                    pn_name = PIAN_NAMES_SHORT.get(pian, "")
                    # 根据篇号找到对应卷号
                    pian_vol = PIAN_VOL.get(f"第{pian}篇", f"第{vol_num}卷")
                    new_text = new_text.replace(old, f"{pian_vol} 第{pian}篇{pn_name} 第{printed_pn}页")
                fixed_annotations += 1
                changed = True
            else:
                range_fallbacks += 1
        
        if changed:
            p.write_text(new_text, "utf-8")
            file_changes[p.name] = new_text.count("第") - text.count("第")  # rough change count
    
    print(f"\n📊 页码修复结果:")
    print(f"  总计标注: {total_annotations} 条")
    print(f"  已转换: {fixed_annotations} 条")
    print(f"  前言/目录(跳过): {deleted_front_matter} 条")
    print(f"  未找到映射: {range_fallbacks} 条")
    print(f"  修改文件: {len(file_changes)} 个")
    print(f"⏱ 总耗时: {(time.time()-t0)*1000:.0f}ms")
    
    # 更新索引
    print("\n🔄 重新生成搜索索引...")
    from build_static_index import main as rebuild_index
    rebuild_index()

if __name__ == "__main__":
    main()