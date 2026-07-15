#!/usr/bin/env python3
"""申万行业轮动折线图 —— 自包含交互式 HTML 生成器(读缓存, 一级/二级 双模式)。

从 fetch_sw_indices 生成的 CSV 缓存读日收盘, 客户端按窗口起点归一化到 100, 单文件 HTML:
- [一级 31 / 二级 123] 一键切换; 二级默认前10强 + 搜索框 + 图例标所属一级
- 图例按窗口末端涨幅排序, 点击隐藏/显示, 悬停高亮; 画布悬停十字线 + tooltip
- 窗口 30/60/120 交易日客户端重算; 前N强/后N弱(一级5 / 二级10)
零依赖(内联 vanilla JS + SVG), 离线可开, 数据 bake 进 HTML。

缓存缺失时自动调 fetch_sw_indices.pull 现拉(自愈, 独立可用)。
用法: python3 chart_industry_rotation.py [--cache PATH] [--outdir DIR] [--days 150]
默认 cache/outdir 均在 ~/Downloads/invest-charts/(仓库外, 不入 git)。
"""
import warnings, io, sys, json, csv, pathlib, argparse
from contextlib import redirect_stderr
warnings.filterwarnings("ignore")

DEFAULT_CACHE = "~/.invest-charts/sw_close.csv"   # 非 TCC 保护目录(Downloads 下 launchd 无写权限)
DEFAULT_OUTDIR = "~/.invest-charts"


def ensure_cache(path, days):
    p = pathlib.Path(path).expanduser()
    if not p.exists():
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
        import fetch_sw_indices as fsi
        rows, *_ = fsi.pull(days, cache_path=str(p))
        fsi.write_cache(rows, p)
    return p


def load_cache(path):
    """CSV → {dates, L1:[{name,closes}], L2:[{name,parent,closes}], asof}; 按 L1 日期轴对齐。"""
    rows = list(csv.DictReader(pathlib.Path(path).expanduser().open(encoding="utf-8")))
    l1dates = sorted({r["date"] for r in rows if r["level"] == "1"})
    dset = set(l1dates)
    by = {}
    for r in rows:
        o = by.setdefault(r["code"], {"name": r["name"], "level": r["level"],
                                      "parent": r["parent"], "map": {}})
        o["map"][r["date"]] = float(r["close"])
    def series_for(level):
        out = []
        for o in by.values():
            if o["level"] != level or not dset.issubset(o["map"]):   # 只留覆盖全部 L1 日期的
                continue
            s = {"name": o["name"], "closes": [round(o["map"][d], 2) for d in l1dates]}
            if level == "2":
                s["parent"] = o["parent"]
            out.append(s)
        return out
    return {"dates": l1dates, "L1": series_for("1"), "L2": series_for("2"),
            "asof": l1dates[-1] if l1dates else None}


FRAGMENT = r"""<style>
.rot-wrap{font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC",sans-serif;color:#1a1a1a;max-width:1080px;margin:0 auto}
.rot-head{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;margin-bottom:6px}
.rot-title{font-size:15px;font-weight:600}
.rot-asof{font-weight:400;color:#888;font-size:12px;margin-left:6px}
.rot-ctrls{font-size:12px;color:#666;display:flex;align-items:center;gap:4px;flex-wrap:wrap}
.rot-ctrls button{font:inherit;border:1px solid #d0d0d0;background:#fff;color:#333;border-radius:5px;padding:3px 9px;cursor:pointer}
.rot-ctrls button:hover{background:#f2f2f2}
.rot-ctrls button.on{background:#2b6cb0;border-color:#2b6cb0;color:#fff}
.rot-ctrls .sep{width:1px;height:16px;background:#e0e0e0;margin:0 3px}
#rot-search{font:inherit;border:1px solid #d0d0d0;border-radius:5px;padding:3px 8px;width:88px;outline:none;color:#333}
#rot-search:focus{border-color:#2b6cb0}
.rot-body{display:flex;gap:10px;align-items:stretch}
#rot-svg{flex:1 1 auto;min-width:0;background:#fff;border:1px solid #eee;border-radius:6px}
.rot-legend{flex:0 0 214px;max-height:520px;overflow-y:auto;font-size:12px;border:1px solid #eee;border-radius:6px;padding:4px}
.rot-li{display:flex;align-items:center;gap:6px;padding:2px 5px;border-radius:4px;cursor:pointer;white-space:nowrap}
.rot-li:hover{background:#f4f7fb}
.rot-li.off{opacity:.32}
.rot-sw{width:11px;height:11px;border-radius:2px;flex:0 0 auto}
.rot-nm{flex:1 1 auto;overflow:hidden;text-overflow:ellipsis}
.rot-par{font-size:10px;color:#aaa;margin-left:4px}
.rot-pct{font-variant-numeric:tabular-nums;font-weight:600}
.rot-tip{position:fixed;pointer-events:none;z-index:9;background:rgba(255,255,255,.97);border:1px solid #ccc;border-radius:6px;padding:7px 9px;font-size:11.5px;box-shadow:0 3px 12px rgba(0,0,0,.14);max-width:230px}
.rot-tip .d{font-weight:600;margin-bottom:3px}
.rot-tip .r{display:flex;justify-content:space-between;gap:10px;font-variant-numeric:tabular-nums}
.rot-note{color:#999;font-size:11px;margin-top:5px}
@media (max-width:680px){.rot-body{flex-direction:column}.rot-legend{flex:1 1 auto;max-height:240px}}
</style>
<div class="rot-wrap">
  <div class="rot-head">
    <div class="rot-title">申万行业轮动 · 归一化累计涨幅<span class="rot-asof" id="rot-asof"></span></div>
    <div class="rot-ctrls">
      <button data-lv="1">一级</button><button data-lv="2">二级</button>
      <span class="sep"></span><span>窗口</span>
      <button data-win="30">30日</button><button data-win="60">60日</button><button data-win="120">120日</button>
      <span class="sep"></span>
      <button id="rot-all">全部</button><button id="rot-top">前5强</button><button id="rot-bot">后5弱</button>
      <input id="rot-search" placeholder="搜行业…">
    </div>
  </div>
  <div class="rot-body">
    <svg id="rot-svg" viewBox="0 0 900 520" preserveAspectRatio="xMidYMid meet"></svg>
    <div class="rot-legend" id="rot-legend"></div>
  </div>
  <div class="rot-note">起点归一化=100，线在 100 上方=区间累计跑赢自身起点。一级=31 板块总览；二级=细分子行业（默认前10强，可搜索，图例标所属一级）。点击图例隐藏/显示，悬停高亮，画布悬停看十字线数值。数据：申万宏源指数日 K。</div>
</div>
<div class="rot-tip" id="rot-tip" style="display:none"></div>
<script>
(function(){
const DATA=__DATA_JSON__;
const SVGNS="http://www.w3.org/2000/svg";
const svg=document.getElementById("rot-svg"),leg=document.getElementById("rot-legend"),tip=document.getElementById("rot-tip"),searchEl=document.getElementById("rot-search");
document.getElementById("rot-asof").textContent="as of "+DATA.asof;
document.querySelector('[data-lv="1"]').textContent="一级 "+DATA.L1.length;
document.querySelector('[data-lv="2"]').textContent="二级 "+DATA.L2.length;
const ND=DATA.dates.length;
const W=900,H=520,mL=46,mR=14,mT=14,mB=26,PW=W-mL-mR,PH=H-mT-mB;
let level=1,SER=DATA.L1,N=SER.length,colors=[],win=120,hidden=new Set(),hi=null,filterMode="all",cross=null,curVis=[],curX=[];

function topN(){return level===1?5:10;}
function mkColors(){colors=SER.map((_,i)=>"hsl("+Math.round(i*360/N)+",68%,50%)");}
function startIdx(){return Math.max(0,ND-win);}
function reb(closes,s){const b=closes[s]; if(!b)return null; const o=[]; for(let i=s;i<ND;i++)o.push(closes[i]/b*100); return o;}
function finalPct(i){const v=reb(SER[i].closes,startIdx()); return v?v[v.length-1]-100:0;}
function el(t,a){const e=document.createElementNS(SVGNS,t); for(const k in a)e.setAttribute(k,a[k]); return e;}

function draw(){
  while(svg.firstChild)svg.removeChild(svg.firstChild);
  const s=startIdx(),n=ND-s,dates=DATA.dates.slice(s);
  const rows=[]; let lo=100,hi2=100;
  for(let i=0;i<N;i++){const v=reb(SER[i].closes,s); if(!v)continue;
    const vis=!hidden.has(i); if(vis){for(const y of v){if(y<lo)lo=y;if(y>hi2)hi2=y;}}
    rows.push({i,v,vis});}
  if(lo===hi2){lo-=1;hi2+=1;} const pad=(hi2-lo)*0.06; lo-=pad; hi2+=pad;
  const xOf=k=>mL+(n<=1?0:k/(n-1)*PW), yOf=y=>mT+(1-(y-lo)/(hi2-lo))*PH;
  curX=dates.map((d,k)=>xOf(k));
  for(let t=0;t<=5;t++){const val=lo+(hi2-lo)*t/5,y=yOf(val);
    svg.appendChild(el("line",{x1:mL,y1:y,x2:W-mR,y2:y,stroke:"#f0f0f0","stroke-width":1}));
    const tx=el("text",{x:mL-6,y:y+3,"text-anchor":"end","font-size":10,fill:"#999"}); tx.textContent=val.toFixed(0); svg.appendChild(tx);}
  const y100=yOf(100); svg.appendChild(el("line",{x1:mL,y1:y100,x2:W-mR,y2:y100,stroke:"#b0b0b0","stroke-width":1,"stroke-dasharray":"3 3"}));
  const xt=Math.min(6,n); for(let t=0;t<xt;t++){const k=Math.round(t*(n-1)/Math.max(1,xt-1)),x=xOf(k);
    const tx=el("text",{x:x,y:H-8,"text-anchor":"middle","font-size":10,fill:"#999"}); tx.textContent=dates[k].slice(5); svg.appendChild(tx);}
  curVis=[];
  for(const r of rows){ if(!r.vis)continue;
    let pts=""; for(let k=0;k<r.v.length;k++)pts+=curX[k].toFixed(1)+","+yOf(r.v[k]).toFixed(1)+" ";
    const faded=hi!==null&&hi!==r.i;
    svg.appendChild(el("polyline",{points:pts.trim(),fill:"none",stroke:colors[r.i],"stroke-width":(hi===r.i?2.6:1.3),opacity:(faded?0.16:0.92),"stroke-linejoin":"round"}));
    curVis.push({i:r.i,v:r.v});}
  cross=el("line",{x1:0,y1:mT,x2:0,y2:mT+PH,stroke:"#888","stroke-width":1,"stroke-dasharray":"2 2",opacity:0,"pointer-events":"none"}); svg.appendChild(cross);
  drawLegend();
}

function drawLegend(){
  leg.innerHTML="";
  const order=SER.map((_,i)=>i).sort((a,b)=>finalPct(b)-finalPct(a));
  for(const i of order){
    const p=finalPct(i),off=hidden.has(i);
    const d=document.createElement("div"); d.className="rot-li"+(off?" off":"");
    const par=SER[i].parent?'<span class="rot-par">'+SER[i].parent+'</span>':'';
    d.innerHTML='<span class="rot-sw" style="background:'+colors[i]+'"></span><span class="rot-nm">'+SER[i].name+par+'</span><span class="rot-pct" style="color:'+(p>=0?"#c0392b":"#218c5a")+'">'+(p>=0?"+":"")+p.toFixed(1)+'%</span>';
    d.onclick=()=>{ if(hidden.has(i))hidden.delete(i); else hidden.add(i); filterMode=hidden.size===0?"all":"custom"; draw(); setFilterBtn(hidden.size===0?"rot-all":null); };
    d.onmouseenter=()=>{hi=i; if(!hidden.has(i))draw();};
    d.onmouseleave=()=>{hi=null; draw();};
    leg.appendChild(d);
  }
}

function setFilterBtn(id){["rot-all","rot-top","rot-bot"].forEach(x=>document.getElementById(x).classList.toggle("on",x===id));}
function applyMode(scroll){
  const q=searchEl.value.trim();
  if(filterMode==="search"&&q){hidden=new Set(); SER.forEach((s,i)=>{if(!s.name.includes(q))hidden.add(i);});}
  else if(filterMode==="all")hidden.clear();
  else if(filterMode==="top"||filterMode==="bot"){
    const order=SER.map((_,i)=>i).sort((a,b)=>finalPct(b)-finalPct(a)),k=topN();
    const keep=new Set(filterMode==="top"?order.slice(0,k):order.slice(-k));
    hidden=new Set(); for(let i=0;i<N;i++)if(!keep.has(i))hidden.add(i);}
  hi=null; draw();
  setFilterBtn(filterMode==="top"?"rot-top":filterMode==="bot"?"rot-bot":filterMode==="all"?"rot-all":null);
  document.getElementById("rot-top").textContent="前"+topN()+"强"; document.getElementById("rot-bot").textContent="后"+topN()+"弱";
  if(scroll)leg.scrollTop=(filterMode==="bot"?leg.scrollHeight:0);
}
function setLevel(lv){
  level=lv; SER=lv===1?DATA.L1:DATA.L2; N=SER.length; mkColors();
  document.querySelectorAll('[data-lv]').forEach(b=>b.classList.toggle("on",+b.dataset.lv===lv));
  searchEl.value=""; filterMode=(lv===1?"all":"top"); applyMode(true);
}
function setWin(w){win=w; document.querySelectorAll('[data-win]').forEach(b=>b.classList.toggle("on",+b.dataset.win===w)); applyMode(false);}
document.querySelectorAll('[data-lv]').forEach(b=>b.onclick=()=>setLevel(+b.dataset.lv));
document.querySelectorAll('[data-win]').forEach(b=>b.onclick=()=>setWin(+b.dataset.win));
document.getElementById("rot-all").onclick=()=>{filterMode="all";searchEl.value="";applyMode(true);};
document.getElementById("rot-top").onclick=()=>{filterMode="top";searchEl.value="";applyMode(true);};
document.getElementById("rot-bot").onclick=()=>{filterMode="bot";searchEl.value="";applyMode(true);};
searchEl.oninput=()=>{filterMode=searchEl.value.trim()?"search":"all"; applyMode(false);};

svg.addEventListener("mousemove",e=>{
  const r=svg.getBoundingClientRect(),sx=(e.clientX-r.left)/r.width*W;
  if(sx<mL||sx>W-mR||!curX.length){tip.style.display="none";cross&&cross.setAttribute("opacity",0);return;}
  let k=0,best=1e9; for(let j=0;j<curX.length;j++){const dd=Math.abs(curX[j]-sx); if(dd<best){best=dd;k=j;}}
  if(cross){cross.setAttribute("x1",curX[k]);cross.setAttribute("x2",curX[k]);cross.setAttribute("opacity",1);}
  const rowsv=curVis.map(o=>({name:SER[o.i].name,color:colors[o.i],val:o.v[k]})).sort((a,b)=>b.val-a.val);
  const show=rowsv.length>16?rowsv.slice(0,8).concat([{name:"…",color:"#ccc",val:null}]).concat(rowsv.slice(-4)):rowsv;
  let html='<div class="d">'+DATA.dates[startIdx()+k]+'</div>';
  for(const o of show)html+='<div class="r"><span style="color:'+o.color+'">■</span><span style="flex:1">'+o.name+'</span><span>'+(o.val==null?"":o.val.toFixed(1))+'</span></div>';
  tip.innerHTML=html; tip.style.display="block";
  let tx=e.clientX+14,ty=e.clientY+12; const tb=tip.getBoundingClientRect();
  if(tx+tb.width>innerWidth)tx=e.clientX-tb.width-14; if(ty+tb.height>innerHeight)ty=innerHeight-tb.height-6;
  tip.style.left=tx+"px"; tip.style.top=ty+"px";
});
svg.addEventListener("mouseleave",()=>{tip.style.display="none";cross&&cross.setAttribute("opacity",0);});

document.querySelector('[data-win="120"]').classList.add("on");
setLevel(1);
})();
</script>"""


def build(cache, outdir, days):
    ensure_cache(cache, days)
    data = load_cache(cache)
    frag = FRAGMENT.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    full = ('<!doctype html><html lang="zh"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>申万行业轮动</title></head><body style="margin:18px;background:#fafafa">'
            + frag + '</body></html>')
    outdir = pathlib.Path(outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)
    fp = outdir / "sw_industry_rotation.html"
    fp.write_text(full, encoding="utf-8")
    (outdir / "sw_industry_rotation.fragment.html").write_text(frag, encoding="utf-8")
    return fp, data


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--outdir", default=DEFAULT_OUTDIR)
    ap.add_argument("--days", type=int, default=150)
    a = ap.parse_args()
    fp, data = build(a.cache, a.outdir, a.days)
    print(f"✅ {fp}  (一级 {len(data['L1'])} + 二级 {len(data['L2'])} × {len(data['dates'])} 交易日, as of {data['asof']})")
