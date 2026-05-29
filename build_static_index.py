#!/usr/bin/env python3
"""构建 GitHub Pages 静态搜索索引"""
import json, re
from pathlib import Path
from collections import Counter

KB = Path(__file__).parent / "机械设计知识库"
OUT = Path(__file__).parent / "static_search.json"
OUT_DOCS = Path(__file__).parent / "docs" / "static_search.json"

EX = {"页码对照表","卷章篇索引","GB标准清单","JB标准清单","设计流程与规范","深化计划","README",".gitignore"}
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
PIAN_VOL = {"第1篇":"第1卷","第2篇":"第1卷","第3篇":"第1卷","第4篇":"第1卷","第5篇":"第1卷",
    "第6篇":"第2卷","第7篇":"第2卷","第8篇":"第2卷","第9篇":"第2卷","第10篇":"第2卷",
    "第11篇":"第2卷","第12篇":"第2卷","第13篇":"第3卷","第14篇":"第3卷","第15篇":"第3卷",
    "第16篇":"第3卷","第17篇":"第4卷","第18篇":"第5卷","第19篇":"第5卷","第20篇":"第5卷",
    "第21篇":"第4卷","第22篇":"第4卷","第23篇":"第5卷",
}
GITHUB_BASE = "https://github.com/nasplycc/mechanical-design-handbook/blob/main/机械设计知识库"

SCENE_TAGS = {
    "传动":["齿轮传动","带传动","链传动"],"齿轮":["齿轮","齿条","齿轮齿条","模数"],
    "轴承":["深沟球","角接触","圆锥滚子","轴承寿命"],"液压":["液压泵","液压缸","液压回路"],
    "材料":["钢材","热处理","调质","淬火"],"弹簧":["压缩弹簧","拉伸弹簧","弹簧设计"],
    "螺纹":["螺栓","螺钉","紧固件"],"键":["平键","花键"],"密封":["润滑","密封","O形圈"],
}

def tokenize(t):
    w = re.findall(r'[\u4e00-\u9fff]{2,6}', t) + re.findall(r'[a-zA-Z0-9.+\-/%*°#≤≥×±→℃]+', t)
    return [x for x in w if len(x) >= 2]

def main():
    index = []
    for p in sorted(KB.rglob("*.md")):
        if p.stem in EX: continue
        try: raw = p.read_text("utf-8")
        except: continue
        rel = str(p.relative_to(KB))
        text = re.sub(r'<!--.*?-->', '', raw)
        
        vol = VOL_G.get(Path(rel).parent.name[:2], "")
        pian = next((m.group(0) for m in re.finditer(r'第\d+篇', raw[:500])), "")
        pv = PIAN_VOL.get(pian, vol)
        
        headings = []
        for m in re.finditer(r'^(#{2,4})\s+(.+)', raw, re.MULTILINE):
            t = m.group(2).strip()
            if len(re.sub(r'[\s\d.()（）\-\—]', '', t)) >= 2:
                headings.append({"l":len(m.group(1)), "t":t})
        
        # 篇范围：从文件头部 来源标注 提取
        sr = ''
        sm = re.search(r'> \*\*来源标注：\*\*.*?第(\d+)卷.*?第(\d+)篇.*?》', raw[:800])
        if sm:
            sr = f"第{sm.group(1)}卷 第{sm.group(2)}篇"
        
        snippets = []
        for line in text.split("\n"):
            ls = line.strip()
            if not ls or ls.startswith("<!--") or ls.startswith("#") or ls.startswith(">"): continue
            if "|" in ls and ("—" in ls or "---" in ls): continue
            clean = re.sub(r'[\|\[\]]', '', ls)[:120]
            if len(clean) >= 15: snippets.append(clean)
            if len(snippets) >= 6: break
        
        tags = []
        for scene, kws in SCENE_TAGS.items():
            for kw in kws:
                if kw in text: tags.append(scene); break
        tags = list(set(tags))
        
        tokens = tokenize(text)
        freq = Counter(tokens)
        top_kws = [w for w,c in freq.most_common(20) if c >= 3][:20]
        
        index.append({
            "f": rel, "gh": f"{GITHUB_BASE}/{rel}", "v": vol or pv, "p": pian, "pn": PIAN_NAMES.get(pian, ""),
            "sr": sr, "h": headings[:15], "s": snippets,
            "t": tags, "kw": top_kws,
        })
    
    data = json.dumps({"index": index}, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(data, "utf-8")
    OUT_DOCS.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOCS.write_text(data, "utf-8")
    print(f"✅ 索引已生成: {len(index)} 文件, {OUT.stat().st_size/1024:.0f} KB, {OUT_DOCS.stat().st_size/1024:.0f} KB (docs)")

if __name__ == "__main__":
    main()