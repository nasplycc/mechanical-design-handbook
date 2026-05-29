#!/usr/bin/env python3
"""
机械设计向导 — 自动生成完整设计报告
输入自然语言描述 → 自动遍历设计流程 → 输出带页码引用的设计报告

用法:
  python3 wizard.py "齿轮齿条 10000N 3m"
  python3 wizard.py "V带传动 7.5kW 1440rpm 传动比3"
  python3 wizard.py -i               # 交互模式
"""
import json, re, sys, time
from pathlib import Path

# 复用 search 引擎
sys.path.insert(0, str(Path(__file__).parent))
from search import parse_query, search_kb, format_search_results, DOMAIN_KEYWORDS, PIAN_NAMES

# ═══════════════════════════
# 设计场景识别
# ═══════════════════════════

SCENE_PATTERNS = [
    # (关键词正则, 场景名, 设计流程步骤)
    (r"(齿轮齿条|齿条.*齿轮|rack.*pinion)", "齿轮齿条机构", [
        "方案设计", "材料选择", "模数初定", "几何参数", "接触强度校核", "弯曲强度校核", "驱动计算", "润滑与结构"
    ]),
    (r"(齿轮传动|圆柱齿轮|斜齿轮|锥齿轮)", "齿轮传动", [
        "方案设计", "材料选择", "模数初定", "几何参数", "接触强度校核", "弯曲强度校核", "精度等级", "润滑"
    ]),
    (r"(V带|带传动|同步带|皮带)", "V带传动", [
        "方案设计", "带型选择", "带轮参数", "中心距与带长", "包角校核", "张紧力", "张紧装置"
    ]),
    (r"(滚子链|链传动|链条|链轮)", "链传动", [
        "方案设计", "链号选择", "链轮参数", "中心距", "润滑方式"
    ]),
    (r"(深沟球|角接触|圆锥滚子|轴承.*选型|轴承.*寿命)", "滚动轴承选型", [
        "工况分析", "轴承类型选择", "尺寸初选", "寿命计算", "当量动载荷", "静载荷校核", "配合选择", "润滑密封"
    ]),
    (r"(压缩弹簧|拉伸弹簧|扭转弹簧|弹簧设计|螺旋弹簧)", "弹簧设计", [
        "工况分析", "材料选择", "参数初定", "几何尺寸", "强度校核", "稳定性校核", "疲劳校核"
    ]),
    (r"(液压系统|液压回路|液压缸|液压泵|液压马达)", "液压系统", [
        "工况分析", "系统方案", "液压缸设计", "泵选型", "阀组选型", "管路计算", "油箱设计"
    ]),
    (r"(螺栓|螺钉|螺纹连接|紧固件|预紧力)", "螺纹连接", [
        "工况分析", "材料与等级", "直径初定", "预紧力计算", "强度校核", "防松设计"
    ]),
    (r"(减速器|齿轮箱|变速器)", "减速器选型/设计", [
        "工况分析", "传动比分配", "齿轮参数", "轴承校核", "轴校核", "润滑与散热"
    ]),
    (r"(轴系|轴设计|转轴|心轴|传动轴|联轴器)", "轴系设计", [
        "工况分析", "材料选择", "轴径估算", "结构设计", "强度校核", "刚度校核", "疲劳校核"
    ]),
]

# 标准数据速查
STANDARD_MODULUS = [1,1.25,1.5,2,2.5,3,4,5,6,8,10,12,16,20,25,32,40,50]

def detect_scene(query):
    """识别设计场景和提取参数"""
    query_lower = query.lower()
    
    scene_name = "通用机械设计"
    steps = ["需求分析", "方案确定", "计算校核", "结构设计"]
    
    for pattern, name, step_list in SCENE_PATTERNS:
        if re.search(pattern, query_lower):
            scene_name = name
            steps = step_list
            break
    
    # 提取参数
    params = {}
    
    # 载荷 (N)
    m = re.search(r'(\d+\.?\d*)\s*[N牛顿吨]', query)
    if m: params["载荷"] = f"{float(m.group(1))} N"
    
    # 力 (N)
    m = re.search(r'(\d+\.?\d*)\s*[kK]?[Nn]', query)
    if m:
        v = float(m.group(1))
        if 'k' in m.group(0).lower()[:m.start()+len(m.group(1))+1]:
            v *= 1000
        params["载荷"] = f"{v} N"
    
    # 行程 (mm/m) - 排除"轴径""直径""宽度"等尺寸干扰
    if not re.search(r'(轴径|直径|宽度|厚度|长度|高度|深度)', query[:20]):
        m = re.search(r'(\d+\.?\d*)\s*(m|mm|厘米)(?!.*(?:轴径|直径|宽度|厚度))', query)
        if m:
            v = float(m.group(1))
            if m.group(2) == 'm': v *= 1000
            if m.group(2) == '厘米': v *= 10
            params["行程"] = f"{v} mm"
    
    # 功率 (kW)
    m = re.search(r'(\d+\.?\d*)\s*k?[Ww]', query)
    if m:
        v = float(m.group(1))
        params["功率"] = f"{v} kW"
    
    # 转速 (rpm/r/min)
    m = re.search(r'(\d+)\s*(rpm|r/min|r/m)', query)
    if m: params["转速"] = f"{m.group(1)} rpm"
    
    # 传动比
    m = re.search(r'传动比\s*[:=]?\s*(\d+\.?\d*)', query)
    if m: params["传动比"] = f"i={m.group(1)}"
    
    return scene_name, steps, params


def render_design_report(scene, steps, params, results):
    """渲染设计报告"""
    lines = [f"⚙️ {scene} 设计报告", "=" * 45]
    
    # 设计输入
    if params:
        lines.append("\n📋 设计输入")
        for k, v in params.items():
            lines.append(f"  {k}: {v}")
    
    # 设计流程
    lines.append(f"\n📐 设计流程（{len(steps)}步）")
    for i, step in enumerate(steps, 1):
        lines.append(f"  {i}. {step}")
    
    # 搜索结果
    if results:
        lines.append(f"\n📖 手册引用")
        for r in results[:4]:
            lines.append(f"\n  📁 {r['file']}")
            loc = f"{r['vol']} {r['pian']}" if r['pian'] else r['vol']
            if r.get('pian_name'): loc += f" {r['pian_name']}"
            lines.append(f"  📍 {loc}")
            if r.get('matches'):
                for m in r['matches'][:2]:
                    lines.append(f"    {m[:100]}")
            if r.get('pages'):
                lines.append(f"  📄 {' | '.join(r['pages'][:3])}")
    
    # 设计向导建议
    lines.append(f"\n💡 设计向导建议")
    suggestions = generate_suggestions(scene, params)
    lines.extend(suggestions)
    
    lines.append(f"\n{'=' * 45}")
    lines.append(f"📌 详细计算请参考对应手册页码")
    
    return "\n".join(lines)


def generate_suggestions(scene, params):
    """生成针对性的设计建议"""
    suggestions = []
    
    if "齿轮齿条" in scene:
        load = params.get("载荷", "0").replace(" N","")
        travel = params.get("行程", "0").replace(" mm","")
        suggestions.append("1️⃣ 材料建议：小齿轮 40Cr 调质，齿条 45钢 调质+高频淬火")
        if load:
            load_n = float(load)
            if load_n > 5000:
                suggestions.append(f"2️⃣ 载荷 {load_n/1000:.1f}kN，建议模数 m=6~8mm，齿数 z=20")
            else:
                suggestions.append(f"2️⃣ 载荷 {load_n:.0f}N，建议模数 m=3~5mm，齿数 z=17~20")
        if travel:
            travel_mm = float(travel)
            suggestions.append(f"3️⃣ 行程 {travel_mm/1000:.1f}m，齿条总长≥行程+齿轮周长+余量")
        suggestions.append("4️⃣ 注意：齿条两端需设限位缓冲，齿轮齿条侧隙控制 ≥0.2mm")
        suggestions.append("5️⃣ 第3卷第15篇 齿轮传动 → 完整几何计算、强度校核公式")
    
    elif "轴承" in scene:
        suggestions.append("1️⃣ 轴承寿命计算：L₁₀ = (C/P)^ε × 10⁶/60n (小时)")
        suggestions.append("2️⃣ 当量动载荷 P = XFr + YFa，查 X/Y 系数表")
        suggestions.append("3️⃣ 第2卷第8篇 轴承 → 完整选型表、尺寸表、寿命计算方法")
    
    elif "V带" in scene or "带传动" in scene:
        suggestions.append("1️⃣ 带型选择：按功率和转速查选型图")
        suggestions.append("2️⃣ 小带轮直径 ≥ d_min，包角 ≥ 120°")
        suggestions.append("3️⃣ 第14篇 带传动 → V带选型表、功率曲线")
    
    elif "液压" in scene:
        suggestions.append("1️⃣ 系统压力等级：低压 2.5~6.3MPa / 中压 10~16MPa / 高压 25~32MPa")
        suggestions.append("2️⃣ 液压缸内径按 F = p·A 计算")
        suggestions.append("3️⃣ 第21篇 液压传动 → 完整设计计算")
    
    else:
        suggestions.append("1️⃣ 参考手册相关篇章进行详细计算")
        suggestions.append("2️⃣ 验证设计条件：载荷、速度、寿命要求")
        suggestions.append("3️⃣ 最终出图前做完整校核")
    
    return suggestions


# ═══════════════════════════
# CLI
# ═══════════════════════════

def main():
    if "-i" in sys.argv:
        print("⚙️ 机械设计向导 (输入 exit 退出)")
        print("例: 齿轮齿条 10000N 3m")
        print("     V带传动 7.5kW 1440rpm")
        while True:
            try:
                q = input("\n🛠️ 设计需求 > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not q or q.lower() in ("exit","quit"):
                break
            
            scene, steps, params = detect_scene(q)
            kws = parse_query(q)
            results = search_kb(kws, 4)
            report = render_design_report(scene, steps, params, results)
            print(f"\n{report}")
        return
    
    query = " ".join(sys.argv[1:])
    if not query:
        print("用法: python3 wizard.py \"齿轮齿条 10000N 3m\"")
        print("      python3 wizard.py -i")
        return
    
    t0 = time.time()
    scene, steps, params = detect_scene(query)
    kws = parse_query(query)
    results = search_kb(kws, 4)
    report = render_design_report(scene, steps, params, results)
    print(report)
    print(f"\n⏱ {(time.time()-t0)*1000:.0f}ms")


if __name__ == "__main__":
    main()