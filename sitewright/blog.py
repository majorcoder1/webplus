"""A blog you write inside WebPlus: posts with pictures and categories, a search box, a reader window,
likes and comments (kept on your own PHP host, with approval before they appear)."""
import datetime
import json
import re
import secrets

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPen

from .basics import TEXT_BASE, new_id
from .webapps import esc

DEFAULTS = dict(w=860, h=640, per_page=6, cols=2, show_image=True, show_excerpt=True, search=True,
                categories=True, cat="", btn="Read more", accent="#2b7de9", card="#ffffff", fill="",
                stroke="", sw=0, radius=8, link="", **dict(TEXT_BASE, size=15))

SCHEMA = [("Blog", [("per_page", "Posts on each page", "int", (1, 50)), ("cols", "Posts across", "int", (1, 4)),
                    ("show_image", "Show each post's picture", "bool", None),
                    ("show_excerpt", "Show a short excerpt", "bool", None),
                    ("search", "Search box", "bool", None), ("categories", "Category buttons", "bool", None),
                    ("cat", "Only show this category (blank for all)", "text", None),
                    ("btn", "Words on the read button", "text", None)]),
          ("Look", [("accent", "Accent colour", "colour", None), ("card", "Post background", "colour!", None),
                    ("fill", "Behind everything", "colour!", None), ("radius", "Corner radius", "int", (0, 40)),
                    ("font", "Font", "font", None), ("size", "Size (px)", "int", (8, 40)),
                    ("color", "Text colour", "colour", None)])]


def default_blog():
    return dict(title="Blog", comments=True, moderate=True, likes=True, key=secrets.token_hex(10), posts=[])


def new_post(title="New post"):
    return dict(id=new_id(), title=title, date=datetime.date.today().isoformat(), author="", category="",
                tags="", asset="", excerpt="", body="Write your post here.\n\nBlank lines start a new paragraph.",
                published=True)


def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:50] or "post"


def slugs(posts):
    """A unique, stable address fragment for each post."""
    seen, out = {}, {}
    for p in posts:
        base = slugify(p["title"])
        n = seen.get(base, 0)
        seen[base] = n + 1
        out[p["id"]] = base if n == 0 else "%s-%d" % (base, n + 1)
    return out


def live_posts(doc, cat=""):
    posts = [p for p in doc.blog["posts"] if p.get("published", True)]
    if cat:
        posts = [p for p in posts if p.get("category", "").strip().lower() == cat.strip().lower()]
    return sorted(posts, key=lambda p: p.get("date", ""), reverse=True)


# -- the little formatting language -------------------------------------------------------------------
def _inline(s, link_for, anames):
    s = esc(s)
    s = re.sub(r"!\[([^\]]*)\]\(asset:([A-Za-z0-9_-]+)\)",
               lambda m: ('<img src="images/%s" alt="%s" loading="lazy">' % (esc(anames[m.group(2)]), m.group(1)))
               if m.group(2) in anames else "", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: '<a href="%s"%s>%s</a>' % (link_for(m.group(2)),
                                                    ' rel="noopener" target="_blank"' if m.group(2).startswith("http") else "",
                                                    m.group(1)), s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def render_body(text, link_for=None, anames=None):
    """Plain writing -> safe HTML. # heading, ## smaller heading, - list, 1. numbered list, > quote,
    **bold**, *italic*, [words](address), ![picture](asset:ID)."""
    link_for = link_for or (lambda u: esc(u) if re.match(r"(https?://|mailto:|#|/)", u) else "#")
    anames = anames or {}

    def safe(u):
        u = u.replace("&amp;", "&")
        return link_for(u)

    out, para, lst, kind = [], [], [], None

    def flush():
        nonlocal para, lst, kind
        if para:
            out.append("<p>%s</p>" % "<br>".join(_inline(x, safe, anames) for x in para))
            para = []
        if lst:
            tag = "ol" if kind == "ol" else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % _inline(x, safe, anames) for x in lst), tag))
            lst, kind = [], None

    for line in (text or "").replace("\r", "").split("\n"):
        s = line.rstrip()
        if not s.strip():
            flush()
            continue
        m = re.match(r"(#{1,3})\s+(.*)", s)
        if m:
            flush()
            out.append("<h%d>%s</h%d>" % (len(m.group(1)) + 1, _inline(m.group(2), safe, anames), len(m.group(1)) + 1))
            continue
        if s.startswith("> "):
            flush()
            out.append("<blockquote>%s</blockquote>" % _inline(s[2:], safe, anames))
            continue
        m = re.match(r"([-*]|\d+[.)])\s+(.*)", s)
        if m:
            k = "ol" if m.group(1)[0].isdigit() else "ul"
            if lst and kind != k:
                flush()
            kind = k
            lst.append(m.group(2))
            continue
        if lst:
            flush()
        para.append(s)
    flush()
    return "\n".join(out)


def plain(text):
    """The words of a post without the formatting marks (for excerpts and search)."""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text or "")
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    lines = []
    for ln in t.replace("\r", "").split("\n"):
        ln = re.sub(r"^\s*(#{1,3}\s+|>\s+|[-*]\s+|\d+[.)]\s+)", "", ln)
        ln = re.sub(r"[*`]+", "", ln)
        if ln.strip():
            lines.append(ln.strip())
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def excerpt_of(p, n=170):
    e = (p.get("excerpt") or "").strip() or plain(p.get("body", ""))
    return e if len(e) <= n else e[:n].rsplit(" ", 1)[0] + "…"


def reading_minutes(p):
    return max(1, round(len(plain(p.get("body", "")).split()) / 200.0))


def pretty_date(iso):
    try:
        d = datetime.date.fromisoformat(iso)
        return "%s %d, %d" % (d.strftime("%B"), d.day, d.year)
    except ValueError:
        return iso


# -- editor drawing ----------------------------------------------------------------------------------
def paint(p, r, d, win):
    doc = win.doc
    if d.get("fill"):
        p.fillRect(r, QColor(d["fill"]))
    p.setPen(QPen(QColor("#c8ced6"), 1, Qt.DashLine))
    p.setBrush(Qt.NoBrush)
    p.drawRect(r.adjusted(.5, .5, -.5, -.5))
    f = QFont(d.get("font", "Sans Serif"))
    f.setPixelSize(int(d.get("size", 15)))
    posts = live_posts(doc, d.get("cat", ""))
    cols = max(int(d.get("cols", 2)), 1)
    pad = 12
    y = r.top() + pad
    if d.get("search") or d.get("categories"):
        p.setPen(QPen(QColor("#b8c0cc"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(r.left() + pad, y, min(r.width() * 0.35, 230), 26), 5, 5)
        p.setPen(QColor("#8a929c"))
        p.setFont(f)
        p.drawText(QRectF(r.left() + pad + 8, y, 200, 26), int(Qt.AlignVCenter), "Search the blog")
        x = r.left() + pad + min(r.width() * 0.35, 230) + 10
        for cat in sorted({q.get("category", "") for q in posts if q.get("category")})[:4]:
            w = f.pixelSize() * len(cat) * 0.62 + 24
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(d.get("accent", "#2b7de9")).lighter(175))
            p.drawRoundedRect(QRectF(x, y + 2, w, 22), 11, 11)
            p.setPen(QColor(d.get("accent", "#2b7de9")).darker(120))
            p.drawText(QRectF(x, y + 2, w, 22), int(Qt.AlignCenter), cat)
            x += w + 6
        y += 40
    gap = 14
    cw = (r.width() - 2 * pad - gap * (cols - 1)) / cols
    ch = 170 if d.get("show_image") else 110
    shown = posts[:int(d.get("per_page", 6))]
    if not shown:
        p.setPen(QColor("#8a929c"))
        p.setFont(f)
        p.drawText(r.adjusted(pad, y, -pad, 0), int(Qt.AlignTop | Qt.TextWordWrap),
                   "No posts yet. Open Tools > Blog manager to write one.")
        return
    for i, post in enumerate(shown):
        cx = r.left() + pad + (i % cols) * (cw + gap)
        cy = y + (i // cols) * (ch + gap)
        if cy + 30 > r.bottom():
            break
        card = QRectF(cx, cy, cw, min(ch, r.bottom() - cy - 4))
        p.setPen(QPen(QColor("#dfe3ea"), 1))
        p.setBrush(QColor(d["card"]) if d.get("card") else Qt.NoBrush)
        p.drawRoundedRect(card, d.get("radius", 8), d.get("radius", 8))
        ty = card.top() + 8
        if d.get("show_image"):
            pm = win.pixmap(post.get("asset")) if post.get("asset") else None
            box = QRectF(card.left() + 1, card.top() + 1, card.width() - 2, min(80, card.height() * 0.45))
            if pm is not None and not pm.isNull():
                k = max(box.width() / pm.width(), box.height() / pm.height())
                p.save()
                p.setClipRect(box)
                p.drawPixmap(QRectF(box.center().x() - pm.width() * k / 2, box.center().y() - pm.height() * k / 2,
                                    pm.width() * k, pm.height() * k), pm, QRectF(pm.rect()))
                p.restore()
            else:
                p.fillRect(box, QColor("#e9edf3"))
            ty = box.bottom() + 6
        fb = QFont(f)
        fb.setBold(True)
        p.setFont(fb)
        p.setPen(QColor(d.get("color", "#222")))
        p.drawText(QRectF(card.left() + 8, ty, card.width() - 16, 20), int(Qt.AlignLeft | Qt.AlignVCenter),
                   post["title"])
        fs = QFont(f)
        fs.setPixelSize(max(int(f.pixelSize() * 0.8), 8))
        p.setFont(fs)
        p.setPen(QColor("#7a8494"))
        p.drawText(QRectF(card.left() + 8, ty + 20, card.width() - 16, 16), int(Qt.AlignLeft),
                   pretty_date(post.get("date", "")) + ("  ·  " + post["category"] if post.get("category") else ""))
        if d.get("show_excerpt"):
            p.setPen(QColor(d.get("color", "#222")))
            p.drawText(QRectF(card.left() + 8, ty + 38, card.width() - 16, max(card.bottom() - ty - 42, 0)),
                       int(Qt.AlignLeft | Qt.TextWordWrap), excerpt_of(post, 90))


# -- the published blog ------------------------------------------------------------------------------
BLOG_CSS = """.bl{box-sizing:border-box;overflow:auto;padding:12px;--ac:#2b7de9;-webkit-overflow-scrolling:touch}
.bl *{box-sizing:border-box}
.bl .bl-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px}
.bl .bl-q{flex:0 1 240px;padding:7px 10px;border:1px solid #b8c0cc;border-radius:6px;font:inherit}
.bl .bl-chip{padding:4px 12px;border:0;border-radius:14px;background:#e8edf4;color:#333;font:inherit;font-size:.9em;cursor:pointer}
.bl .bl-chip.on{background:var(--ac);color:#fff}
.bl .bl-list{display:grid;gap:14px;grid-template-columns:repeat(var(--cols,2),minmax(0,1fr))}
.bl .bp{display:none}.bl .bp.show{display:block}
.bl .bp-card{display:block;height:100%;border:1px solid #dfe3ea;border-radius:var(--rad,8px);overflow:hidden;text-decoration:none;color:inherit;background:var(--card,#fff);transition:box-shadow .2s}
.bl .bp-card:hover{box-shadow:0 4px 14px rgba(0,0,0,.14)}
.bl .bp-card img{display:block;width:100%;height:150px;object-fit:cover}
.bl .bp-in{padding:10px 12px}
.bl .bp-t{font-weight:bold;font-size:1.1em;margin-bottom:4px}
.bl .bp-m{font-size:.8em;color:#7a8494;margin-bottom:6px}
.bl .bp-x{font-size:.92em;line-height:1.45}
.bl .bp-more{display:inline-block;margin-top:8px;color:var(--ac);font-weight:bold;font-size:.9em}
.bl .bp-stats{margin-top:6px;font-size:.8em;color:#7a8494}
.bl .bl-pg{display:flex;gap:6px;justify-content:center;margin-top:16px;flex-wrap:wrap}
.bl .bl-pg button{min-width:34px;padding:5px 10px;border:1px solid #cfd6e0;background:#fff;border-radius:5px;font:inherit;cursor:pointer}
.bl .bl-pg button.on{background:var(--ac);border-color:var(--ac);color:#fff}
.bl .bl-none{padding:20px;color:#7a8494}
.bl-modal{position:fixed;inset:0;z-index:9000;background:rgba(15,20,30,.72);display:none;align-items:flex-start;justify-content:center;overflow:auto;padding:24px 12px}
.bl-modal.open{display:flex}
.bl-win{background:#fff;color:#222;max-width:760px;width:100%;border-radius:10px;padding:26px 30px;position:relative;font:16px/1.65 sans-serif;box-shadow:0 10px 40px rgba(0,0,0,.4)}
.bl-win h1{font-size:1.9em;line-height:1.25;margin:0 0 6px}
.bl-win .bw-m{color:#7a8494;font-size:.88em;margin-bottom:14px}
.bl-win .bw-img{width:100%;max-height:380px;object-fit:cover;border-radius:8px;margin:0 0 16px}
.bl-win .bw-b p,.bl-win .bw-b ul,.bl-win .bw-b ol,.bl-win .bw-b blockquote{margin:0 0 1em}
.bl-win .bw-b h2,.bl-win .bw-b h3,.bl-win .bw-b h4{margin:1.2em 0 .4em;line-height:1.25}
.bl-win .bw-b ul,.bl-win .bw-b ol{padding-left:1.4em}
.bl-win .bw-b blockquote{border-left:4px solid var(--ac,#2b7de9);padding:2px 0 2px 14px;color:#555;font-style:italic}
.bl-win .bw-b img{max-width:100%;border-radius:6px}.bl-win .bw-b a{color:var(--ac,#2b7de9)}
.bl-win .bw-x{position:absolute;right:12px;top:8px;border:0;background:none;font-size:30px;line-height:1;cursor:pointer;color:#666}
.bl-win .bw-bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:18px 0;padding:12px 0;border-top:1px solid #e3e7ee;border-bottom:1px solid #e3e7ee}
.bl-win .bw-bar button,.bl-win .bw-bar a{padding:5px 12px;border:1px solid #cfd6e0;background:#fff;border-radius:16px;font:inherit;font-size:.85em;cursor:pointer;color:#333;text-decoration:none}
.bl-win .bw-like.on{background:#ffe9ec;border-color:#f3a6b2;color:#c0213a}
.bl-win h3.bw-ch{font-size:1.15em;margin:18px 0 8px}
.bl-win .bw-c{padding:10px 0;border-bottom:1px solid #eef0f4}
.bl-win .bw-c b{display:block}.bl-win .bw-c small{color:#8a929c}
.bl-win .bw-c div{white-space:pre-wrap;overflow-wrap:anywhere}
.bl-win form.bw-f{display:grid;gap:8px;margin-top:12px}
.bl-win form.bw-f input[type=text],.bl-win form.bw-f textarea{padding:8px 10px;border:1px solid #b8c0cc;border-radius:6px;font:inherit;width:100%}
.bl-win form.bw-f textarea{min-height:90px;resize:vertical}
.bl-win form.bw-f .hp{position:absolute;left:-9999px}
.bl-win form.bw-f button{justify-self:start;padding:8px 20px;border:0;border-radius:6px;background:var(--ac,#2b7de9);color:#fff;font:inherit;cursor:pointer}
.bl-win .bw-note{font-size:.9em;color:#555;margin-top:4px}
.bl-win .bw-nav{display:flex;justify-content:space-between;gap:10px;margin-top:20px;font-size:.9em}
.bl-win .bw-nav a{color:var(--ac,#2b7de9);cursor:pointer}
@media(max-width:600px){.bl-win{padding:20px 16px}}"""

BLOG_JS = r"""<script>
(function(){
var root=document.getElementById(__ID__),API=__API__,COMMENTS=__COMMENTS__,LIKES=__LIKES__,PER=__PER__;
if(!root)return;
var posts=[].slice.call(root.querySelectorAll('.bp')),q=root.querySelector('.bl-q'),chips=[].slice.call(root.querySelectorAll('.bl-chip'));
var pager=root.querySelector('.bl-pg'),none=root.querySelector('.bl-none'),cat='',page=1,stats={},apiOK=false;
function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML;}
function visible(){var t=q?q.value.toLowerCase().trim():'';return posts.filter(function(p){
  return(!cat||p.getAttribute('data-cat')===cat)&&(!t||p.getAttribute('data-s').indexOf(t)>-1);});}
function draw(){
  var v=visible(),pages=Math.max(1,Math.ceil(v.length/PER));if(page>pages)page=pages;
  posts.forEach(function(p){p.classList.remove('show');});
  v.slice((page-1)*PER,page*PER).forEach(function(p){p.classList.add('show');});
  none.style.display=v.length?'none':'block';
  pager.innerHTML='';
  if(pages>1)for(var i=1;i<=pages;i++){(function(i){var b=document.createElement('button');b.type='button';b.textContent=i;
    if(i===page)b.className='on';b.onclick=function(){page=i;draw();root.scrollTop=0;};pager.appendChild(b);})(i);}
  showStats();
}
function showStats(){posts.forEach(function(p){var s=stats[p.getAttribute('data-id')],el=p.querySelector('.bp-stats');
  if(!el)return;var t=[];if(s&&LIKES)t.push('♥ '+s.likes);if(s&&COMMENTS)t.push('💬 '+s.comments);el.textContent=t.join('   ');});}
if(q)q.addEventListener('input',function(){page=1;draw();});
chips.forEach(function(c){c.onclick=function(){cat=c.getAttribute('data-c');chips.forEach(function(x){x.classList.toggle('on',x===c);});page=1;draw();};});
function api(qs,body){return fetch(API+qs,body?{method:'POST',body:body}:{cache:'no-store'}).then(function(r){return r.json().then(function(j){j._status=r.status;return j;});});}
if(COMMENTS||LIKES)api('?a=stats').then(function(s){if(s&&!s.error){stats=s;apiOK=true;showStats();}}).catch(function(){});
// ---- reader window
var modal=document.createElement('div');modal.className='bl-modal';modal.style.setProperty('--ac',getComputedStyle(root).getPropertyValue('--ac'));
modal.innerHTML='<div class="bl-win" role="dialog" aria-modal="true"></div>';document.body.appendChild(modal);
var win=modal.firstChild,cur=null;
function slugOf(p){return p.id.replace(/^post-/,'');}
function openPost(p,push){
  cur=p;var full=p.querySelector('.bp-full'),id=p.getAttribute('data-id');
  var img=p.getAttribute('data-img');
  var list=visible(),i=list.indexOf(p),prev=i>0?list[i-1]:null,next=i>-1&&i<list.length-1?list[i+1]:null;
  var url=location.href.split('#')[0]+'#'+p.id,enc=encodeURIComponent(url),ttl=encodeURIComponent(p.getAttribute('data-t'));
  win.innerHTML='<button class="bw-x" aria-label="Close">×</button><h1>'+esc(p.getAttribute('data-t'))+'</h1><div class="bw-m">'+esc(p.getAttribute('data-m'))+'</div>'
   +(img?'<img class="bw-img" src="'+esc(img)+'" alt="">':'')+'<div class="bw-b">'+full.innerHTML+'</div>'
   +'<div class="bw-bar"><span>Share:</span><button type="button" class="bw-copy">Copy link</button>'
   +'<a target="_blank" rel="noopener" href="https://www.facebook.com/sharer/sharer.php?u='+enc+'">Facebook</a>'
   +'<a target="_blank" rel="noopener" href="https://twitter.com/intent/tweet?url='+enc+'&text='+ttl+'">X</a>'
   +'<a href="mailto:?subject='+ttl+'&body='+enc+'">Email</a>'
   +(LIKES&&apiOK?'<button type="button" class="bw-like">♥ <span>'+((stats[id]||{}).likes||0)+'</span></button>':'')+'</div>'
   +'<div class="bw-cm"></div>'
   +'<div class="bw-nav"><span>'+(prev?'<a class="bw-p">← '+esc(prev.getAttribute('data-t'))+'</a>':'')+'</span><span>'+(next?'<a class="bw-n">'+esc(next.getAttribute('data-t'))+' →</a>':'')+'</span></div>';
  modal.classList.add('open');modal.scrollTop=0;document.documentElement.style.overflow='hidden';
  if(push!==false&&location.hash!=='#'+p.id)history.replaceState(null,'','#'+p.id);
  win.querySelector('.bw-x').onclick=closePost;
  win.querySelector('.bw-copy').onclick=function(){var b=this;(navigator.clipboard?navigator.clipboard.writeText(url):Promise.reject()).then(function(){b.textContent='Copied!';},function(){prompt('Copy this link',url);});};
  var pp=win.querySelector('.bw-p'),nn=win.querySelector('.bw-n');if(pp)pp.onclick=function(){openPost(prev);};if(nn)nn.onclick=function(){openPost(next);};
  var lk=win.querySelector('.bw-like');
  if(lk){if(localStorage.getItem('swl_'+id))lk.classList.add('on');lk.onclick=function(){
    var fd=new FormData();fd.append('a','like');fd.append('p',id);
    api('',fd).then(function(j){if(j.likes!=null){(stats[id]=stats[id]||{comments:0}).likes=j.likes;lk.querySelector('span').textContent=j.likes;lk.classList.add('on');try{localStorage.setItem('swl_'+id,'1');}catch(e){}showStats();}});};}
  if(COMMENTS&&apiOK)comments(id);
}
function comments(id){
  var box=win.querySelector('.bw-cm');box.innerHTML='<h3 class="bw-ch">Comments</h3><div class="bw-list">Loading…</div>'
   +'<form class="bw-f"><input type="text" name="name" maxlength="60" placeholder="Your name" required><textarea name="text" maxlength="2000" placeholder="Write a comment" required></textarea>'
   +'<input class="hp" type="text" name="website" tabindex="-1" autocomplete="off"><button type="submit">Post comment</button><div class="bw-note"></div></form>';
  var t0=Date.now(),list=box.querySelector('.bw-list'),f=box.querySelector('form'),note=box.querySelector('.bw-note');
  api('?a=comments&p='+encodeURIComponent(id)).then(function(j){
    var c=j.comments||[];list.innerHTML=c.length?c.map(function(x){return'<div class="bw-c"><b>'+esc(x.name)+'</b><small>'+esc(x.when)+'</small><div>'+esc(x.text)+'</div></div>';}).join(''):'<div class="bw-note">No comments yet. Be the first.</div>';});
  try{var nm=localStorage.getItem('swl_name');if(nm)f.name.value=nm;}catch(e){}
  f.onsubmit=function(e){e.preventDefault();var fd=new FormData(f);fd.append('a','comment');fd.append('p',id);fd.append('t',String(Date.now()-t0));
    try{localStorage.setItem('swl_name',f.name.value);}catch(e){}
    note.textContent='Sending…';
    api('',fd).then(function(j){if(j.ok){note.textContent=j.pending?'Thank you! Your comment will appear once it has been approved.':'Thank you!';f.text.value='';
        if(!j.pending)comments(id);}else note.textContent=j.error||'The comment could not be sent.';}).catch(function(){note.textContent='The comment could not be sent.';});};
}
function closePost(){modal.classList.remove('open');document.documentElement.style.overflow='';cur=null;if(location.hash.indexOf('#post-')===0)history.replaceState(null,'',location.href.split('#')[0]);}
modal.addEventListener('click',function(e){if(e.target===modal)closePost();});
document.addEventListener('keydown',function(e){if(!cur)return;if(e.key==='Escape')closePost();});
posts.forEach(function(p){p.querySelector('.bp-card').addEventListener('click',function(e){e.preventDefault();openPost(p);});});
function fromHash(){var h=location.hash.slice(1),p=h&&posts.filter(function(x){return x.id===h;})[0];if(p)openPost(p,false);}
window.addEventListener('hashchange',fromHash);
draw();fromHash();
})();
</script>"""


def export(d, css, files, anames, doc, tag, attr):
    from . import extras
    from .export import _page_css, resolve_link
    posts = live_posts(doc, d.get("cat", ""))
    sl = slugs(doc.blog["posts"])
    bid = "bl-" + re.sub(r"[^A-Za-z0-9_-]", "", str(d.get("id", "x")))[:40]
    cats = sorted({p.get("category", "").strip() for p in posts if p.get("category", "").strip()}, key=str.lower)
    bar = ""
    if d.get("search"):
        bar += '<input class="bl-q" type="search" placeholder="Search the blog" aria-label="Search the blog">'
    if d.get("categories") and cats:
        bar += '<button type="button" class="bl-chip on" data-c="">All</button>' + "".join(
            '<button type="button" class="bl-chip" data-c="%s">%s</button>' % (esc(c), esc(c)) for c in cats)

    def link_for(u):
        return esc(resolve_link(u, files)) if u.startswith(("page:", "anchor:")) else (
            esc(u) if re.match(r"(https?://|mailto:|#|/)", u) else "#")

    arts = []
    for p in posts:
        meta = pretty_date(p.get("date", ""))
        if p.get("author"):
            meta += "  ·  " + p["author"]
        if p.get("category"):
            meta += "  ·  " + p["category"]
        meta += "  ·  %d min read" % reading_minutes(p)
        img = "images/" + anames[p["asset"]] if p.get("asset") in anames else ""
        card_img = '<img src="%s" alt="" loading="lazy">' % esc(img) if img and d.get("show_image") else ""
        ex = '<div class="bp-x">%s</div>' % esc(excerpt_of(p)) if d.get("show_excerpt") else ""
        search = " ".join([p["title"], p.get("category", ""), p.get("tags", ""), plain(p.get("body", ""))]).lower()
        arts.append(
            '<article class="bp" id="post-%s" data-id="%s" data-cat="%s" data-t="%s" data-m="%s" data-img="%s" data-s="%s">'
            '<a class="bp-card" href="#post-%s">%s<div class="bp-in"><div class="bp-t">%s</div><div class="bp-m">%s</div>%s'
            '<span class="bp-more">%s &rarr;</span><div class="bp-stats"></div></div></a>'
            '<div class="bp-full" hidden>%s</div></article>' % (
                sl[p["id"]], esc(p["id"]), esc(p.get("category", "").strip()), esc(p["title"]), esc(meta), esc(img),
                esc(search[:600]), sl[p["id"]], card_img, esc(p["title"]),
                esc(pretty_date(p.get("date", "")) + (("  ·  " + p["category"]) if p.get("category") else "")), ex,
                esc(d.get("btn", "Read more")), render_body(p.get("body", ""), link_for, anames)))
    if BLOG_CSS not in _page_css:
        _page_css.append(BLOG_CSS)
    bl = doc.blog
    extras.CONTEXT["scripts"].append(
        BLOG_JS.replace("__ID__", json.dumps(bid)).replace("__API__", json.dumps(extras.CONTEXT.get("prefix", "") + "blog-api.php"))
        .replace("__COMMENTS__", "true" if bl.get("comments") else "false").replace("__LIKES__", "true" if bl.get("likes") else "false")
        .replace("__PER__", str(max(int(d.get("per_page", 6)), 1))))
    bg = "background:%s;" % d["fill"] if d.get("fill") else ""
    return ('<div class="o bl" id="%s" style="%s;%s--ac:%s;--cols:%d;--card:%s;--rad:%dpx;%s">'
            '<div class="bl-bar">%s</div><div class="bl-list">%s</div><div class="bl-none" style="display:none">No posts found.</div>'
            '<div class="bl-pg"></div></div>'
            % (bid, css, bg, d.get("accent", "#2b7de9"), max(int(d.get("cols", 2)), 1), d.get("card") or "transparent",
               d.get("radius", 8), extras.text_css(d), bar, "".join(arts)))


API_PHP = r"""<?php
// Blog likes and comments. Data is kept in blog-data/ (closed to visitors).
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$POSTS = array(%(posts)s);
$CFG = array('comments' => %(comments)s, 'moderate' => %(moderate)s, 'likes' => %(likes)s, 'notify' => %(notify)s,
             'site' => %(site)s, 'key' => %(key)s);
$dir = __DIR__ . '/blog-data';
if (!is_dir($dir)) { @mkdir($dir, 0755, true); }
if (!file_exists($dir . '/.htaccess')) {
    @file_put_contents($dir . '/.htaccess', "Require all denied\n<IfModule !mod_authz_core.c>\nDeny from all\n</IfModule>\n");
    @file_put_contents($dir . '/index.html', '');
}
function sw_len($s) { return function_exists('mb_strlen') ? mb_strlen($s) : strlen($s); }
$secret = hash('sha256', __FILE__ . php_uname('n'));
$ip = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '';
$who = substr(hash('sha256', $ip . $secret), 0, 20);

function sw_load($file, $default) {
    if (!is_file($file)) { return $default; }
    $j = json_decode((string)@file_get_contents($file), true);
    return is_array($j) ? $j : $default;
}
function sw_update($file, $default, $fn) {
    $fh = fopen($file, 'c+');
    if (!$fh) { return null; }
    flock($fh, LOCK_EX);
    $j = json_decode((string)stream_get_contents($fh), true);
    if (!is_array($j)) { $j = $default; }
    $res = $fn($j);
    ftruncate($fh, 0); rewind($fh);
    fwrite($fh, json_encode($j)); fflush($fh);
    flock($fh, LOCK_UN); fclose($fh);
    return $res;
}
function sw_fail($code, $msg) { http_response_code($code); echo json_encode(array('error' => $msg)); exit; }

$a = isset($_REQUEST['a']) ? (string)$_REQUEST['a'] : '';
$p = isset($_REQUEST['p']) ? preg_replace('/[^A-Za-z0-9_-]/', '', (string)$_REQUEST['p']) : '';
$cfile = $dir . '/comments.json';
$lfile = $dir . '/likes.json';

if ($a === 'stats') {
    $c = sw_load($cfile, array());
    $l = sw_load($lfile, array());
    $out = array();
    foreach ($POSTS as $id) { $out[$id] = array('likes' => isset($l[$id]['count']) ? (int)$l[$id]['count'] : 0, 'comments' => 0); }
    foreach ($c as $x) { if (!empty($x['ok']) && isset($out[$x['post']])) { $out[$x['post']]['comments']++; } }
    echo json_encode($out); exit;
}
if ($a === 'comments') {
    if (!in_array($p, $POSTS, true)) { sw_fail(404, 'Unknown post'); }
    $out = array();
    foreach (sw_load($cfile, array()) as $x) {
        if (!empty($x['ok']) && $x['post'] === $p) { $out[] = array('name' => $x['name'], 'text' => $x['text'], 'when' => gmdate('M j, Y', $x['ts'])); }
    }
    echo json_encode(array('comments' => $out)); exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { sw_fail(400, 'Nothing to do'); }
if (!in_array($p, $POSTS, true)) { sw_fail(404, 'Unknown post'); }
if ($a === 'like') {
    if (!$CFG['likes']) { sw_fail(403, 'Likes are off'); }
    $cookie = 'swb_' . $p;
    $res = sw_update($lfile, array(), function (&$l) use ($p, $who, $cookie) {
        if (!isset($l[$p])) { $l[$p] = array('count' => 0, 'who' => array()); }
        if (isset($_COOKIE[$cookie]) || in_array($who, $l[$p]['who'], true)) { return (int)$l[$p]['count']; }
        $l[$p]['count']++;
        $l[$p]['who'][] = $who;
        if (count($l[$p]['who']) > 5000) { $l[$p]['who'] = array_slice($l[$p]['who'], -5000); }
        return (int)$l[$p]['count'];
    });
    setcookie('swb_' . $p, '1', time() + 31536000, '/');
    echo json_encode(array('likes' => $res)); exit;
}
if ($a === 'comment') {
    if (!$CFG['comments']) { sw_fail(403, 'Comments are off'); }
    if (!empty($_POST['website'])) { echo json_encode(array('ok' => true, 'pending' => true)); exit; }     // robot trap
    $name = trim(preg_replace('/\s+/', ' ', isset($_POST['name']) ? (string)$_POST['name'] : ''));
    $text = trim(isset($_POST['text']) ? str_replace("\r", '', (string)$_POST['text']) : '');
    $t = isset($_POST['t']) ? (int)$_POST['t'] : 0;
    if (sw_len($name) < 1 || sw_len($name) > 60) { sw_fail(400, 'Please give your name.'); }
    if (sw_len($text) < 2 || sw_len($text) > 2000) { sw_fail(400, 'Please write a comment (up to 2000 characters).'); }
    if ($t < 2500) { sw_fail(429, 'That was quick. Please read it over and try again.'); }
    if (preg_match_all('~https?://~i', $text) > 2) { sw_fail(400, 'Please use no more than two links.'); }
    $now = time();
    $pending = $CFG['moderate'];
    $res = sw_update($cfile, array(), function (&$c) use ($p, $name, $text, $who, $now, $pending) {
        $recent = 0;
        foreach ($c as $x) { if ($x['who'] === $who && $x['ts'] > $now - 600) { $recent++; } }
        if ($recent >= 5) { return 'rate'; }
        foreach ($c as $x) { if ($x['who'] === $who && $x['post'] === $p && $x['text'] === $text) { return 'dup'; } }
        $c[] = array('id' => bin2hex(random_bytes(6)), 'post' => $p, 'name' => $name, 'text' => $text, 'ts' => $now,
                     'ok' => !$pending, 'who' => $who);
        if (count($c) > 5000) { $c = array_slice($c, -5000); }
        return 'ok';
    });
    if ($res === 'rate') { sw_fail(429, 'Too many comments. Please wait a few minutes.'); }
    if ($res === 'dup') { sw_fail(400, 'You already posted that.'); }
    if ($res !== 'ok') { sw_fail(500, 'The comment could not be saved.'); }
    if ($CFG['notify']) {
        $host = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : 'your site';
        $link = (isset($_SERVER['HTTPS']) ? 'https://' : 'http://') . $host . rtrim(dirname($_SERVER['SCRIPT_NAME']), '/') . '/blog-admin.php?key=' . $CFG['key'];
        @mail($CFG['notify'], 'New blog comment on ' . $CFG['site'],
              "From: " . $name . "\n\n" . $text . "\n\n" . ($pending ? "It is waiting for your approval:\n" : "Manage comments:\n") . $link,
              "Content-Type: text/plain; charset=utf-8");
    }
    echo json_encode(array('ok' => true, 'pending' => $pending)); exit;
}
sw_fail(400, 'Nothing to do');
"""

ADMIN_PHP = r"""<?php
// Approve or delete blog comments. Open this page with your secret key.
$KEY = %(key)s;
$POSTS = array(%(titles)s);
header('X-Robots-Tag: noindex');
$k = isset($_REQUEST['key']) ? (string)$_REQUEST['key'] : '';
if (!hash_equals($KEY, $k)) { http_response_code(403); echo 'Not allowed.'; exit; }
$file = __DIR__ . '/blog-data/comments.json';
$all = is_file($file) ? json_decode((string)file_get_contents($file), true) : array();
if (!is_array($all)) { $all = array(); }
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['id'], $_POST['do'])) {
    foreach ($all as $i => $x) {
        if ($x['id'] === $_POST['id']) {
            if ($_POST['do'] === 'approve') { $all[$i]['ok'] = true; }
            if ($_POST['do'] === 'delete') { unset($all[$i]); }
        }
    }
    file_put_contents($file, json_encode(array_values($all)), LOCK_EX);
    header('Location: ?key=' . urlencode($KEY)); exit;
}
function h($s) { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
?><!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Blog comments</title>
<style>body{font:16px/1.5 sans-serif;max-width:760px;margin:20px auto;padding:0 14px;color:#222}
.c{border:1px solid #dde2ea;border-radius:8px;padding:10px 14px;margin:10px 0}.c small{color:#788}
.c.p{border-color:#e8b04a;background:#fff8e8}button{padding:5px 14px;margin-right:6px;cursor:pointer}
form{display:inline}pre{white-space:pre-wrap;font:inherit;margin:6px 0}</style></head><body>
<h1>Blog comments</h1>
<?php
$pend = array_filter($all, function ($x) { return empty($x['ok']); });
echo '<h2>Waiting for you (' . count($pend) . ')</h2>';
foreach (array_reverse($all) as $x) {
    if (!empty($x['ok'])) { continue; }
    echo '<div class="c p"><b>' . h($x['name']) . '</b> <small>on ' . h(isset($POSTS[$x['post']]) ? $POSTS[$x['post']] : $x['post']) . ', ' . gmdate('M j, Y H:i', $x['ts']) . ' UTC</small><pre>' . h($x['text']) . '</pre>'
       . '<form method="post"><input type="hidden" name="key" value="' . h($KEY) . '"><input type="hidden" name="id" value="' . h($x['id']) . '"><button name="do" value="approve">Approve</button><button name="do" value="delete">Delete</button></form></div>';
}
echo '<h2>Showing on the site</h2>';
foreach (array_reverse($all) as $x) {
    if (empty($x['ok'])) { continue; }
    echo '<div class="c"><b>' . h($x['name']) . '</b> <small>on ' . h(isset($POSTS[$x['post']]) ? $POSTS[$x['post']] : $x['post']) . ', ' . gmdate('M j, Y', $x['ts']) . '</small><pre>' . h($x['text']) . '</pre>'
       . '<form method="post"><input type="hidden" name="key" value="' . h($KEY) . '"><input type="hidden" name="id" value="' . h($x['id']) . '"><button name="do" value="delete">Delete</button></form></div>';
}
?></body></html>
"""


def php_files(doc, kinds):
    if "blog" not in kinds:
        return {}
    from .phpgen import _q
    bl = doc.blog
    posts = [p for p in bl["posts"] if p.get("published", True)]            # drafts take no likes or comments
    ids = [p["id"] for p in posts]
    titles = ", ".join("%s => %s" % (_q(p["id"]), _q(p["title"])) for p in posts)
    notify = doc.form_email or ""
    return {
        "blog-api.php": API_PHP % dict(
            posts=", ".join(_q(i) for i in ids), comments="true" if bl.get("comments") else "false",
            moderate="true" if bl.get("moderate") else "false", likes="true" if bl.get("likes") else "false",
            notify=_q(notify) if notify else "false", site=_q(doc.site_title), key=_q(bl["key"])),
        "blog-admin.php": ADMIN_PHP % dict(key=_q(bl["key"]), titles=titles),
    }


KINDS = {"blog": dict(name="Blog", defaults=DEFAULTS, schema=SCHEMA, paint=paint, export=export,
                      on_insert=lambda win, d: _first_post(win))}


def _first_post(win):
    if not win.doc.blog["posts"]:
        p = new_post("Welcome to the blog")
        p["body"] = ("This is your first post. Open **Tools > Blog manager** to change it or write new ones.\n\n"
                     "- Search, category buttons and a reader window come with the blog\n"
                     "- Readers can like posts and leave comments (you approve them first)\n\n"
                     "> Posts keep their order by date, newest first.")
        win.doc.blog["posts"].append(p)
