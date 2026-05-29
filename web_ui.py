import http.server, json, re, urllib.parse, os, mimetypes
from pathlib import Path

KB = Path("/vol2/1000/working/机械设计原理/机械设计知识库")
BASE = Path("/vol2/1000/working/机械设计原理")

# 加载印刷页码→PDF页码反向映射
_PIAN_MAPS = {}
def _load_pian_map(vol):
    if vol in _PIAN_MAPS:
        return _PIAN_MAPS[vol]
    fp = BASE / f".pian_map_v{vol}.json"
    if not fp.exists():
        return None
    with open(fp) as f:
        raw = json.load(f)
    # raw: {pdf_pn: [pian, printed_pn]} 转为 {(pian, printed_pn): pdf_pn}
    rev = {}
    for pdf_pn, (pian, printed_pn) in raw.items():
        rev[(int(pian), int(printed_pn))] = int(pdf_pn)
    _PIAN_MAPS[vol] = rev
    return rev

def _lookup_pdf_page(vol_num, pian, page):
    m = _load_pian_map(vol_num)
    if m is None:
        return None
    return m.get((int(pian), int(page)))
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

# PDF 文件映射
PDF_FILES = {
    "1": BASE / "机械设计手册 第六版 第1卷.PDF",
    "2": BASE / "机械设计手册 第六版 第2卷.PDF",
    "3": BASE / "-机械设计手册 第六版 第3卷.PDF",
    "4": BASE / "-机械设计手册 第六版 第4卷.PDF",
    "5": BASE / "-机械设计手册 第六版 第5卷.PDF",
}

print("📚 加载知识库...", file=__import__('sys').stderr)
FILES = {}
for p in sorted(KB.rglob("*.md")):
    if p.stem in EX: continue
    rel = str(p.relative_to(KB))
    try: t = p.read_text("utf-8")
    except: continue
    vol = VOL_G.get(Path(rel).parent.name[:2], "")
    pian = next((m.group(0) for m in re.finditer(r'第\d+篇', t[:500])), "")
    FILES[rel] = {"text":t,"vol":vol,"pian":pian,"pn":PIAN_NAMES.get(pian,"")}

DOMAIN = {
    "传动":["齿轮传动","带传动","链传动"],"齿轮":["齿轮","齿条","齿轮齿条","斜齿轮","模数"],
    "轴承":["深沟球","角接触","圆锥滚子","轴承寿命"],"弹簧":["压缩弹簧","拉伸弹簧","弹簧设计"],
    "液压":["液压泵","液压缸","溢流阀","液压回路"],"材料":["45钢","40Cr","热处理","调质"],
    "螺纹":["螺栓","螺钉","紧固件"],"键":["平键","花键"],"密封":["润滑","密封","O形圈"],
}

def search(q, mr=5):
    terms = set()
    for kws in DOMAIN.values():
        for kw in kws:
            if kw in q: terms.add(kw)
    for w in re.findall(r'[\u4e00-\u9fff]{4,6}', q): terms.add(w)
    for w in re.findall(r'[\u4e00-\u9fff]{2,3}', q):
        if len(w)>=2: terms.add(w)
    res = []
    for rel, d in FILES.items():
        t = d["text"]; s = 0
        for w in terms:
            c = t.count(w)
            if c: s += c*(5 if len(w)>=4 else 2)
        if not s: continue
        ml = []
        for ln in t.split("\n"):
            ls = ln.strip()
            if not ls or ls.startswith("<!--"): continue
            for w in terms:
                if w in ls: ml.append(ls[:150]); break
            if len(ml)>=3: break
        # 篇范围（不展示不精确的具体页码）
        sr = ''
        sm = re.search(r'> \*\*来源标注：\*\*.*?第(\d+)卷.*?第(\d+)篇.*?》', t[:800])
        if sm:
            sr = f"第{sm.group(1)}卷 第{sm.group(2)}篇"
        gh_url = f"https://github.com/nasplycc/mechanical-design-handbook/blob/main/机械设计知识库/{rel}"
        res.append({"file":rel,"gh":gh_url,"sr":sr,"score":s,"vol":d["vol"],"pian":d["pian"],"pn":d["pn"],"matches":ml})
    res.sort(key=lambda r:-r["score"])
    return res[:mr]

HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📚 机械设计手册查询</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<style>
*{box-sizing:border-box}
body{font-family:-apple-system,sans-serif;background:#f5f6fa;color:#2d3436;max-width:900px;margin:0 auto;padding:20px}
h1{font-size:24px}.s{display:flex;gap:8px;margin:16px 0}
.s input{flex:1;padding:12px;border:2px solid #dfe6e9;border-radius:10px;font-size:15px;outline:none}
.s input:focus{border-color:#0984e3}
.s button{padding:12px 24px;background:#0984e3;color:#fff;border:none;border-radius:10px;font-size:15px;cursor:pointer}
.q a{display:inline-block;padding:6px 14px;background:#dfe6e9;border-radius:20px;font-size:13px;color:#2d3436;text-decoration:none;margin:3px}
.r{background:#fff;border-radius:12px;padding:16px;margin-bottom:12px;border:1px solid #eee}
.r h2{font-size:14px;color:#0984e3;margin:0 0 4px}
.r .l{font-size:12px;color:#636e72;margin-bottom:4px}
.r .m{font-size:13px;color:#555;line-height:1.6;padding-left:8px;border-left:3px solid #dfe6e9;margin:8px 0}
.r .p span{display:inline-block;margin:2px}
.r .p a{display:inline-block;background:#e8f4fd;padding:2px 10px;border-radius:4px;font-size:12px;color:#e67e22;text-decoration:none;border:1px solid #ffe0b0;cursor:pointer}
.r .p a:hover{background:#fef3e0;border-color:#e67e22}

#ld{display:none;text-align:center;padding:30px;color:#636e72}
#mt{font-size:12px;color:#b2bec3;text-align:center;margin-top:20px}
</style></head>
<body>
<h1>📚 机械设计手册</h1>
<p style="font-size:13px;color:#636e72">成大先主编 · 5卷8512页 · 点页码直接跳转PDF</p>
<div class="s"><input id="q" placeholder="如：齿轮齿条 / 45号钢热处理 / 深沟球轴承" onkeydown="if(event.key==='Enter')go()"><button onclick="go()">查询</button></div>
<div class="q">
<a href="javascript:setQ('齿轮齿条机构')">⚙️ 齿轮齿条</a>
<a href="javascript:setQ('深沟球轴承选型')">🔧 轴承</a>
<a href="javascript:setQ('45号钢调质处理')">🔩 45号钢</a>
<a href="javascript:setQ('V带传动设计')">⛓️ V带</a>
<a href="javascript:setQ('液压系统回路')">💧 液压</a>
<a href="javascript:setQ('压缩弹簧设计')">🌀 弹簧</a>
</div>
<div id="ld">🔍 查询中...</div>
<div id="rs"></div>
<div id="mt"></div>
<script>
function setQ(q){document.getElementById('q').value=q;go()}
function go(){
  let q=document.getElementById('q').value.trim()
  if(!q)return
  document.getElementById('ld').style.display='block'
  document.getElementById('rs').innerHTML=''
  fetch('/s?q='+encodeURIComponent(q)).then(r=>r.json()).then(d=>{
    document.getElementById('ld').style.display='none'
    if(!d.r||!d.r.length){document.getElementById('rs').innerHTML='<p style="text-align:center;color:#636e72">😕 未找到</p>';return}
    let h=''
    d.r.forEach(r=>{
      let loc=(r.vol||'')+' '+(r.pian||'')+' '+(r.pn||'')
      let pp = r.sr ? '<span style="background:#e8f4fd;padding:2px 8px;border-radius:4px;font-size:12px;color:#636e72">📖 '+r.sr+' 范围</span>' : '';
      let mm=(r.matches||[]).map(m=>m+'<br>').join('')
      h+='<div class="r"><h2>📁 <a href="'+r.gh+'" target="_blank" style="color:#0984e3;text-decoration:none">'+r.file+'</a> <a href="'+r.gh+'" target="_blank" style="font-size:11px;color:#636e72;text-decoration:none;vertical-align:super">↗</a></h2><div class="l">📍 '+loc+'</div><div class="m">'+mm+'</div><div class="p">'+pp+'</div></div>'
    })
    document.getElementById('rs').innerHTML=h
    document.getElementById('mt').textContent='🔍 '+q+' · '+d.r.length+'条 · '+d.t+'ms'
    // 渲染 LaTeX 公式
    try{renderMathInElement(document.getElementById('rs'),{delimiters:[{left:'$',right:'$',display:false},{left:'$$',right:'$$',display:true}],macros:{"\\text":"\\text"}})}catch(e){}
  }).catch(()=>{document.getElementById('ld').style.display='none';document.getElementById('rs').innerHTML='<p style="text-align:center;color:#e74c3c">❌ 失败</p>'})
}
</script></body></html>"""

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        
        if path == "/s":
            q = params.get("q", [""])[0]
            import time; t0=time.time()
            r = search(q)
            dt = int((time.time()-t0)*1000)
            self.send_response(200); self.send_header("Content-Type","application/json;charset=utf-8")
            self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
            self.wfile.write(json.dumps({"r":r,"t":dt},ensure_ascii=False).encode())
            return
        
        # PDF 直跳: /pdf/3#page=820
        if path.startswith("/pdf/"):
            vol_num = path[5:].strip("/")
            pdf_path = PDF_FILES.get(vol_num)
            if pdf_path and pdf_path.exists():
                size = pdf_path.stat().st_size
                range_hdr = self.headers.get("Range")
                encoded_name = urllib.parse.quote(f'di{vol_num}juan.PDF')
                if range_hdr:
                    # 支持 Range 分段下载（浏览器PDF查看器需要）
                    m = re.match(r"bytes=(\d+)-(\d*)", range_hdr)
                    if m:
                        start = int(m.group(1))
                        end = int(m.group(2)) if m.group(2) else size - 1
                        cl = end - start + 1
                        self.send_response(206)
                        self.send_header("Content-Type","application/pdf")
                        self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
                        self.send_header("Content-Length",str(cl))
                        self.send_header("Accept-Ranges","bytes")
                        self.end_headers()
                        with open(pdf_path,"rb") as f:
                            f.seek(start)
                            remaining = cl
                            while remaining:
                                chunk = f.read(min(65536, remaining))
                                if not chunk: break
                                self.wfile.write(chunk)
                                remaining -= len(chunk)
                        return
                # 全量返回（流式分块）
                self.send_response(200)
                self.send_header("Content-Type","application/pdf")
                self.send_header("Content-Length",str(size))
                self.send_header("Accept-Ranges","bytes")
                self.send_header("Content-Disposition", f"inline; filename*=UTF-8''{encoded_name}")
                self.send_header("X-Frame-Options", "SAMEORIGIN")
                self.end_headers()
                with open(pdf_path,"rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk: break
                        self.wfile.write(chunk)
                return
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"PDF not found")
            return
        
        # HTML 页面
        self.send_response(200); self.send_header("Content-Type","text/html;charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))
    
    def log_message(self, *a): pass

if __name__ == "__main__":
    http.server.HTTPServer(("0.0.0.0",5231), H).serve_forever()