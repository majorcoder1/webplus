"""A shop: products you list in WebPlus, product cards and a cart on the page, and checkout through
PayPal, Stripe, Shopify or WooCommerce. Money never passes through WebPlus or this program: the buyer
pays at the payment company (or your own Shopify / WooCommerce store)."""
import csv
import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPen

from .basics import TEXT_BASE, new_id
from .webapps import esc

PROVIDERS = [("paypal", "PayPal"), ("stripe", "Stripe (cards, Apple Pay, Google Pay)"),
             ("shopify", "Shopify store"), ("woocommerce", "WooCommerce store")]
CURRENCIES = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "CA$", "AUD": "A$", "NZD": "NZ$", "JPY": "¥",
              "CHF": "CHF ", "SEK": "kr ", "NOK": "kr ", "DKK": "kr ", "MXN": "MX$", "BRL": "R$", "INR": "₹",
              "PLN": "zł ", "ZAR": "R "}
ZERO_DECIMAL = {"JPY", "KRW", "HUF", "TWD", "CLP"}

DEFAULT_CARD = dict(w=260, h=380, product="", btn="Add to cart", show_image=True, show_desc=True, buy_now=False,
                    accent="#2b7de9", card="#ffffff", stroke="#dfe3ea", sw=1, radius=8, link="",
                    **dict(TEXT_BASE, size=15))


def default_shop():
    return dict(currency="USD", provider="paypal", paypal_client="", paypal_email="", stripe_secret="",
                shopify_domain="", shopify_token="", woo_url="", shipping=0.0, tax=0.0,
                thanks="Thank you for your order!", products=[])


def new_product(name="New product"):
    return dict(id=new_id(), name=name, price=10.0, desc="", asset="", image_url="", sku="", active=True,
                shopify_variant="", woo_id="", stripe_link="")


def decimals(cur):
    return 0 if cur in ZERO_DECIMAL else 2


def money(v, cur="USD"):
    sym = CURRENCIES.get(cur, cur + " ")
    n = decimals(cur)
    return "%s{:,.{n}f}".format(float(v), n=n) % sym


def find(doc, pid):
    return next((p for p in doc.shop["products"] if p["id"] == pid), None)


def active(doc):
    return [p for p in doc.shop["products"] if p.get("active", True)]


# -- editor drawing ---------------------------------------------------------------------------------
def _card(p, r, d, win, prod, grid_pad=0):
    shop = win.doc.shop
    p.setPen(QPen(QColor(d["stroke"]), d.get("sw", 1)) if d.get("stroke") and d.get("sw") else Qt.NoPen)
    p.setBrush(QColor(d["card"]) if d.get("card") else Qt.NoBrush)
    p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), d.get("radius", 8), d.get("radius", 8))
    f = QFont(d.get("font", "Sans Serif"))
    f.setPixelSize(int(d.get("size", 15)))
    y = r.top() + 1
    if d.get("show_image", True):
        box = QRectF(r.left() + 1, y, r.width() - 2, r.height() * 0.5)
        pm = win.pixmap(prod.get("asset")) if prod and prod.get("asset") else None
        if pm is not None and not pm.isNull():
            k = max(box.width() / pm.width(), box.height() / pm.height())
            p.save()
            p.setClipRect(box)
            p.drawPixmap(QRectF(box.center().x() - pm.width() * k / 2, box.center().y() - pm.height() * k / 2,
                                pm.width() * k, pm.height() * k), pm, QRectF(pm.rect()))
            p.restore()
        else:
            p.fillRect(box, QColor("#e9edf3"))
            p.setPen(QColor("#98a2b3"))
            p.setFont(f)
            p.drawText(box, int(Qt.AlignCenter), "Product picture" if prod else "Choose a product")
        y = box.bottom() + 8
    fb = QFont(f)
    fb.setBold(True)
    p.setFont(fb)
    p.setPen(QColor(d.get("color", "#222")))
    p.drawText(QRectF(r.left() + 10, y, r.width() - 20, f.pixelSize() * 1.6), int(Qt.AlignLeft | Qt.AlignVCenter),
               prod["name"] if prod else "(no product chosen)")
    y += f.pixelSize() * 1.7
    p.setFont(f)
    p.setPen(QColor(d.get("accent", "#2b7de9")))
    p.drawText(QRectF(r.left() + 10, y, r.width() - 20, f.pixelSize() * 1.6), int(Qt.AlignLeft | Qt.AlignVCenter),
               money(prod["price"], shop["currency"]) if prod else "")
    y += f.pixelSize() * 1.8
    if d.get("show_desc", True) and prod:
        p.setPen(QColor("#5b6675"))
        fs = QFont(f)
        fs.setPixelSize(max(int(f.pixelSize() * 0.9), 8))
        p.setFont(fs)
        p.drawText(QRectF(r.left() + 10, y, r.width() - 20, max(r.bottom() - y - 48, 0)),
                   int(Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap), prod.get("desc", ""))
    br = QRectF(r.left() + 10, r.bottom() - 40, r.width() - 20, 30)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(d.get("accent", "#2b7de9")))
    p.drawRoundedRect(br, 5, 5)
    p.setPen(QColor("#ffffff"))
    p.setFont(fb)
    p.drawText(br, int(Qt.AlignCenter), d.get("btn", "Add to cart"))


def paint_product(p, r, d, win):
    _card(p, r, d, win, find(win.doc, d.get("product")))


def paint_grid(p, r, d, win):
    prods = active(win.doc)
    cols = max(int(d.get("cols", 3)), 1)
    gap = 14
    cw = (r.width() - gap * (cols - 1)) / cols
    ch = float(d.get("card_h", 330))
    if not prods:
        p.setPen(QColor("#8a929c"))
        p.drawText(r.adjusted(10, 10, -10, 0), int(Qt.AlignTop | Qt.TextWordWrap),
                   "Product grid. Add products in Tools > Shop manager.")
        return
    for i, prod in enumerate(prods):
        x = r.left() + (i % cols) * (cw + gap)
        y = r.top() + (i // cols) * (ch + gap)
        if y + 30 > r.bottom():
            break
        _card(p, QRectF(x, y, cw, min(ch, r.bottom() - y)), d, win, prod)


def paint_cart(p, r, d, win):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(d.get("accent", "#2b7de9")))
    p.drawRoundedRect(r, d.get("radius", 8), d.get("radius", 8))
    f = QFont(d.get("font", "Sans Serif"))
    f.setPixelSize(int(d.get("size", 15)))
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor(d.get("color", "#ffffff")))
    p.drawText(r, int(Qt.AlignCenter), "\U0001f6d2 %s (0)  %s" % (d.get("label", "Cart"), money(0, win.doc.shop["currency"])))


# -- the published shop ---------------------------------------------------------------------------------
SHOP_CSS = """.sw-prod{box-sizing:border-box;overflow:hidden;display:flex;flex-direction:column;--ac:#2b7de9}
.sw-prod *{box-sizing:border-box}
.sw-prod img{display:block;width:100%;flex:0 0 50%;min-height:0;object-fit:cover}
.sw-pi{padding:8px 10px;display:flex;flex-direction:column;flex:1;min-height:0}
.sw-pn{font-weight:bold;line-height:1.3}.sw-pp{color:var(--ac);margin:2px 0 4px}
.sw-pd{font-size:.9em;color:#5b6675;overflow:hidden;flex:1}
.sw-add,.sw-cartbtn{border:0;border-radius:6px;background:var(--ac);color:#fff;font:inherit;font-weight:bold;cursor:pointer;padding:8px 10px}
.sw-add{margin-top:6px;width:100%}.sw-add:hover,.sw-cartbtn:hover{filter:brightness(1.1)}
.sw-grid{display:grid;gap:14px;grid-template-columns:repeat(var(--cols,3),minmax(0,1fr));overflow:auto;align-content:start}
.sw-grid .sw-prod{position:relative;left:auto;top:auto;width:auto;height:var(--ch,330px)}
.sw-over{position:fixed;inset:0;background:rgba(15,20,30,.5);z-index:9000;display:none}
.sw-over.open{display:block}
.sw-panel{position:fixed;top:0;right:0;bottom:0;width:min(420px,100vw);background:#fff;color:#222;z-index:9001;
transform:translateX(105%);transition:transform .25s;display:flex;flex-direction:column;font:15px/1.45 sans-serif;box-shadow:-6px 0 30px rgba(0,0,0,.3)}
.sw-panel.open{transform:none}
.sw-ph{display:flex;justify-content:space-between;align-items:center;padding:14px 16px;border-bottom:1px solid #e3e7ee;font-weight:bold;font-size:1.15em}
.sw-ph button{border:0;background:none;font-size:28px;line-height:1;cursor:pointer;color:#666}
.sw-pl{flex:1;overflow:auto;padding:6px 16px}
.sw-li{display:grid;grid-template-columns:56px 1fr auto;gap:10px;align-items:center;padding:10px 0;border-bottom:1px solid #eef0f4}
.sw-li img{width:56px;height:56px;object-fit:cover;border-radius:6px;background:#eef}
.sw-li .nm{font-weight:bold}.sw-li small{color:#788}
.sw-q{display:inline-flex;align-items:center;gap:6px;margin-top:4px}
.sw-q button{width:26px;height:26px;border:1px solid #cfd6e0;border-radius:50%;background:#fff;cursor:pointer;font:inherit}
.sw-x{border:0;background:none;color:#b33;cursor:pointer;font:inherit;font-size:.85em}
.sw-pf{padding:12px 16px;border-top:1px solid #e3e7ee}
.sw-tt{display:flex;justify-content:space-between;margin:2px 0}.sw-tt.big{font-weight:bold;font-size:1.15em;margin-top:6px}
.sw-co{margin-top:10px}
.sw-co button,.sw-co a.sw-b{display:block;width:100%;text-align:center;padding:11px;border:0;border-radius:6px;background:var(--sw-ac,#2b7de9);color:#fff;font:inherit;font-weight:bold;cursor:pointer;text-decoration:none;margin-top:6px}
.sw-msg{margin-top:8px;font-size:.9em;color:#555}.sw-none{padding:30px 0;color:#788;text-align:center}
.sw-toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#222;color:#fff;padding:10px 18px;border-radius:8px;z-index:9100;font:15px sans-serif;opacity:0;pointer-events:none;transition:opacity .25s}
.sw-toast.on{opacity:1}"""

SHOP_JS = r"""<script>
(function(){
if(window.SWSHOPINIT)return;window.SWSHOPINIT=1;
var S=window.SWSHOP,P=S.p,KEY='swcart:'+location.host,hasBtn=!!document.querySelector('[data-cart]');
function load(){try{return JSON.parse(localStorage.getItem(KEY))||{};}catch(e){return{};}}
function save(){try{localStorage.setItem(KEY,JSON.stringify(cart));}catch(e){}}
var cart=load();
function fmt(n){var s=n.toLocaleString(undefined,{minimumFractionDigits:S.dec,maximumFractionDigits:S.dec});return S.sym+s;}
function lines(){var o=[];for(var id in cart){if(P[id]&&cart[id]>0)o.push({id:id,q:cart[id],p:P[id]});}return o;}
function totals(){var s=0,l=lines();l.forEach(function(x){s+=x.p.p*x.q;});s=Math.round(s*100)/100;
  var sh=l.length?S.ship:0,tx=Math.round(s*S.tax)/100;return{s:s,sh:sh,tx:tx,t:Math.round((s+sh+tx)*100)/100,n:l.reduce(function(a,x){return a+x.q;},0)};}
function el(tag,cls,txt){var e=document.createElement(tag);if(cls)e.className=cls;if(txt!=null)e.textContent=txt;return e;}
var over=el('div','sw-over'),panel=el('div','sw-panel'),toast=el('div','sw-toast');
panel.setAttribute('role','dialog');panel.setAttribute('aria-label','Shopping cart');
if(S.ac)panel.style.setProperty('--sw-ac',S.ac);
document.body.appendChild(over);document.body.appendChild(panel);document.body.appendChild(toast);
function say(t){toast.textContent=t;toast.classList.add('on');clearTimeout(say.t);say.t=setTimeout(function(){toast.classList.remove('on');},2200);}
function open(){render();over.classList.add('open');panel.classList.add('open');}
function close(){over.classList.remove('open');panel.classList.remove('open');}
over.onclick=close;document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
function badge(){var t=totals();[].forEach.call(document.querySelectorAll('[data-cart]'),function(b){
  b.textContent='🛒 '+(b.getAttribute('data-label')||'Cart')+' ('+t.n+')  '+fmt(t.s);});}
function set(id,q){if(q<=0)delete cart[id];else cart[id]=Math.min(q,99);save();badge();if(panel.classList.contains('open'))render();}
function add(id,q){if(!P[id])return;set(id,(cart[id]||0)+(q||1));}
// ---- checkout
var ppLoaded=0,ppWait=[];
function paypalSDK(cb){
  if(window.paypal)return cb();ppWait.push(cb);if(ppLoaded)return;ppLoaded=1;
  var s=document.createElement('script');s.src='https://www.paypal.com/sdk/js?client-id='+encodeURIComponent(S.pp.client)+'&currency='+S.cur+'&components=buttons';
  s.onload=function(){ppWait.forEach(function(f){f();});};s.onerror=function(){ppLoaded=0;ppWait=[];};document.head.appendChild(s);
}
function amt(n){return n.toFixed(S.dec);}
function checkout(box,msg){
  var l=lines(),t=totals();box.innerHTML='';
  if(!l.length)return;
  if(S.prov==='paypal'){
    if(S.pp.client){
      var c=el('div');box.appendChild(c);
      paypalSDK(function(){
        if(!window.paypal||!c.isConnected)return;
        paypal.Buttons({
          createOrder:function(d,a){var t=totals(),l=lines();return a.order.create({purchase_units:[{
            amount:{currency_code:S.cur,value:amt(t.t),breakdown:{item_total:{currency_code:S.cur,value:amt(t.s)},
              shipping:{currency_code:S.cur,value:amt(t.sh)},tax_total:{currency_code:S.cur,value:amt(t.tx)}}},
            items:l.map(function(x){return{name:x.p.n.slice(0,126),sku:(x.p.k||'').slice(0,50),quantity:String(x.q),unit_amount:{currency_code:S.cur,value:amt(x.p.p)}};})}]});},
          onApprove:function(d,a){return a.order.capture().then(function(){cart={};save();badge();render();msg.textContent=S.thanks;});},
          onError:function(){msg.textContent='PayPal could not complete that. Please try again.';}
        }).render(c);
      });
    }else if(S.pp.email){
      var f=el('form');f.method='post';f.action='https://www.paypal.com/cgi-bin/webscr';
      function h(n,v){var i=el('input');i.type='hidden';i.name=n;i.value=v;f.appendChild(i);}
      h('cmd','_cart');h('upload','1');h('business',S.pp.email);h('currency_code',S.cur);h('charset','utf-8');
      l.forEach(function(x,i){h('item_name_'+(i+1),x.p.n);h('amount_'+(i+1),amt(x.p.p));h('quantity_'+(i+1),x.q);});
      if(t.sh)h('handling_cart',amt(t.sh));if(t.tx)h('tax_cart',amt(t.tx));
      h('return',location.href.split('#')[0].split('?')[0]+'?paid=1');h('cancel_return',location.href.split('#')[0]);
      var b=el('button',null,'Pay with PayPal');b.type='submit';f.appendChild(b);box.appendChild(f);
    }else msg.textContent='PayPal is not set up yet (Tools > Shop manager).';
  }else if(S.prov==='stripe'){
    var b=el('button',null,'Checkout');b.type='button';box.appendChild(b);
    b.onclick=function(){b.disabled=true;msg.textContent='One moment…';
      fetch(S.api,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:lines().map(function(x){return{id:x.id,q:x.q};}),back:location.href.split('#')[0].split('?')[0]})})
       .then(function(r){return r.json();}).then(function(j){b.disabled=false;if(j.url){location.href=j.url;}else msg.textContent=j.error||'Checkout could not start.';})
       .catch(function(){b.disabled=false;msg.textContent='Checkout needs a web host that runs PHP.';});};
  }else if(S.prov==='shopify'){
    var miss=l.filter(function(x){return !x.p.v;});
    if(miss.length){msg.textContent='Some items are not linked to Shopify yet.';return;}
    var a=el('a','sw-b','Checkout at '+S.shop.domain);a.href='https://'+S.shop.domain+'/cart/'+l.map(function(x){return x.p.v+':'+x.q;}).join(',');box.appendChild(a);
  }else if(S.prov==='woocommerce'){
    l.forEach(function(x){if(!x.p.w)return;var a=el('a','sw-b',(l.length>1?'Buy '+x.p.n:'Checkout')+' at the store');
      a.href=S.shop.woo.replace(/\/$/,'')+'/?add-to-cart='+encodeURIComponent(x.p.w)+'&quantity='+x.q;box.appendChild(a);});
    if(l.length>1)msg.textContent='The store takes one product at a time. Buy each one with its button.';
  }
}
function render(){
  panel.innerHTML='';
  var hd=el('div','sw-ph');hd.appendChild(el('span',null,'Your cart'));var x=el('button',null,'×');x.setAttribute('aria-label','Close');x.onclick=close;hd.appendChild(x);panel.appendChild(hd);
  var list=el('div','sw-pl'),l=lines();panel.appendChild(list);
  if(!l.length){list.appendChild(el('div','sw-none','Your cart is empty.'));}
  l.forEach(function(it){
    var row=el('div','sw-li'),im=el('img');if(it.p.i)im.src=it.p.i;im.alt='';row.appendChild(im);
    var mid=el('div');mid.appendChild(el('div','nm',it.p.n));mid.appendChild(el('small',null,fmt(it.p.p)+' each'));
    var q=el('div','sw-q'),m=el('button',null,'−'),n=el('span',null,String(it.q)),pl=el('button',null,'+');m.type=pl.type='button';
    m.onclick=function(){set(it.id,it.q-1);};pl.onclick=function(){set(it.id,it.q+1);};q.appendChild(m);q.appendChild(n);q.appendChild(pl);
    var rm=el('button','sw-x','Remove');rm.type='button';rm.onclick=function(){set(it.id,0);};q.appendChild(rm);mid.appendChild(q);row.appendChild(mid);
    row.appendChild(el('div',null,fmt(it.p.p*it.q)));list.appendChild(row);});
  var t=totals(),ft=el('div','sw-pf');panel.appendChild(ft);
  function tt(a,b,big){var r=el('div','sw-tt'+(big?' big':''));r.appendChild(el('span',null,a));r.appendChild(el('span',null,b));ft.appendChild(r);}
  if(l.length){tt('Subtotal',fmt(t.s));if(t.sh)tt('Shipping',fmt(t.sh));if(t.tx)tt('Tax',fmt(t.tx));tt('Total',fmt(t.t),1);}
  var box=el('div','sw-co'),msg=el('div','sw-msg');ft.appendChild(box);ft.appendChild(msg);
  checkout(box,msg);
}
document.addEventListener('click',function(e){
  var a=e.target.closest('[data-add]');
  if(a){var id=a.getAttribute('data-add');if(a.hasAttribute('data-buy')&&P[id]&&P[id].l){location.href=P[id].l;return;}
    add(id,1);if(a.hasAttribute('data-buy')||!hasBtn)open();else say('Added to your cart');return;}
  if(e.target.closest('[data-cart]'))open();
});
if(/[?&]paid=1/.test(location.search)){cart={};save();history.replaceState(null,'',location.href.replace(/[?&]paid=1/,''));setTimeout(function(){say(S.thanks);},300);}
badge();
})();
</script>"""


def _catalog(doc, anames):
    out = {}
    for p in active(doc):
        img = ("images/" + anames[p["asset"]]) if p.get("asset") in anames else p.get("image_url", "")
        out[p["id"]] = dict(n=p["name"], p=round(float(p["price"]), 2), i=img, k=p.get("sku", ""),
                            v=str(p.get("shopify_variant", "")).strip(), w=str(p.get("woo_id", "")).strip(),
                            l=p.get("stripe_link", "").strip() if re.match(r"https://", p.get("stripe_link", "").strip()) else "")
    return out


def _page_boot(doc, anames, accent):
    """The shop's settings and product list, once per page (before the cart script)."""
    from . import extras
    ctx = extras.CONTEXT
    if ctx.get("shop_booted"):
        return
    ctx["shop_booted"] = True
    s = doc.shop
    cfg = dict(cur=s["currency"], sym=CURRENCIES.get(s["currency"], s["currency"] + " "), dec=decimals(s["currency"]),
               prov=s["provider"], pp=dict(client=s.get("paypal_client", "").strip(), email=s.get("paypal_email", "").strip()),
               ship=float(s.get("shipping") or 0), tax=float(s.get("tax") or 0), api=ctx.get("prefix", "") + "stripe-checkout.php",
               thanks=s.get("thanks", ""), ac=accent,
               shop=dict(domain=re.sub(r"[^A-Za-z0-9.-]", "", re.sub(r"^https?://", "", s.get("shopify_domain", "").strip()).split("/")[0]),
                         woo=s.get("woo_url", "").strip() if re.match(r"https?://", s.get("woo_url", "").strip()) else ""), p=_catalog(doc, anames))
    blob = json.dumps(cfg).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    ctx["scripts"].append("<script>window.SWSHOP=%s;</script>" % blob)
    ctx["scripts"].append(SHOP_JS)


def _card_html(d, prod, doc, anames, style, cls="o sw-prod"):
    cur = doc.shop["currency"]
    img = ""
    if d.get("show_image", True):
        src = ("images/" + anames[prod["asset"]]) if prod.get("asset") in anames else prod.get("image_url", "")
        if src:
            img = '<img src="%s" alt="%s" loading="lazy">' % (esc(src), esc(prod["name"]))
        else:
            img = '<div style="flex:0 0 50%%;background:#e9edf3"></div>'
    desc = '<div class="sw-pd">%s</div>' % esc(prod.get("desc", "")) if d.get("show_desc", True) else '<div class="sw-pd"></div>'
    buy = " data-buy" if d.get("buy_now") else ""
    return ('<div class="%s" itemscope itemtype="https://schema.org/Product" style="%s">%s<div class="sw-pi">'
            '<div class="sw-pn" itemprop="name">%s</div><div class="sw-pp">%s</div>%s'
            '<button type="button" class="sw-add" data-add="%s"%s>%s</button></div></div>'
            % (cls, style, img, esc(prod["name"]), esc(money(prod["price"], cur)), desc, esc(prod["id"]), buy,
               esc(d.get("btn", "Add to cart"))))


def _look(d):
    from .extras import text_css
    bg = "background:%s;" % d["card"] if d.get("card") else ""
    border = "border:%dpx solid %s;" % (d["sw"], d["stroke"]) if d.get("stroke") and d.get("sw") else ""
    return "%s%sborder-radius:%dpx;--ac:%s;%s" % (bg, border, d.get("radius", 8), d.get("accent", "#2b7de9"), text_css(d))


def export_product(d, css, files, anames, doc, tag, attr):
    from .export import _page_css
    prod = find(doc, d.get("product"))
    if not prod or not prod.get("active", True):
        return ""
    if SHOP_CSS not in _page_css:
        _page_css.append(SHOP_CSS)
    _page_boot(doc, anames, d.get("accent"))
    return _card_html(d, prod, doc, anames, css + ";" + _look(d))


def export_grid(d, css, files, anames, doc, tag, attr):
    from .export import _page_css
    if SHOP_CSS not in _page_css:
        _page_css.append(SHOP_CSS)
    _page_boot(doc, anames, d.get("accent"))
    cards = "".join(_card_html(d, p, doc, anames, "", "sw-prod") for p in active(doc))
    return ('<div class="o sw-grid" style="%s;--cols:%d;--ch:%dpx;%s">%s</div>'
            % (css, max(int(d.get("cols", 3)), 1), int(d.get("card_h", 330)), _look(d), cards))


def export_cart(d, css, files, anames, doc, tag, attr):
    from .export import _page_css
    if SHOP_CSS not in _page_css:
        _page_css.append(SHOP_CSS)
    _page_boot(doc, anames, d.get("accent"))
    from .extras import text_css
    return ('<button type="button" class="o sw-cartbtn" data-cart data-label="%s" style="%s;%s;background:%s;color:%s;'
            'border-radius:%dpx">%s (0)</button>' % (esc(d.get("label", "Cart")), css, text_css(d), d.get("accent", "#2b7de9"),
                                                      d.get("color", "#ffffff"), d.get("radius", 8), esc(d.get("label", "Cart"))))


# -- Stripe: the one PHP file ---------------------------------------------------------------------------
STRIPE_PHP = r"""<?php
// Starts a Stripe Checkout payment. Prices come from the list kept in shop-private/, never from the visitor's browser.
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
function sw_fail($code, $msg) { http_response_code($code); echo json_encode(array('error' => $msg)); exit; }
$cfg = @include __DIR__ . '/shop-private/config.php';
if (!is_array($cfg) || empty($cfg['stripe_secret'])) { sw_fail(500, 'Stripe is not set up yet.'); }
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { sw_fail(405, 'Use the checkout button.'); }
$in = json_decode((string)file_get_contents('php://input'), true);
if (!is_array($in) || empty($in['items']) || !is_array($in['items']) || count($in['items']) > 50) { sw_fail(400, 'Your cart is empty.'); }
$cur = strtolower($cfg['currency']);
$zero = in_array(strtoupper($cfg['currency']), array('JPY', 'KRW', 'HUF', 'TWD', 'CLP'), true);
$mult = $zero ? 1 : 100;
$f = array('mode' => 'payment');
$i = 0; $sub = 0;
foreach ($in['items'] as $it) {
    $id = isset($it['id']) ? (string)$it['id'] : '';
    $q = isset($it['q']) ? (int)$it['q'] : 0;
    if (!isset($cfg['products'][$id]) || $q < 1 || $q > 99) { sw_fail(400, 'An item in your cart is not available any more.'); }
    $p = $cfg['products'][$id];
    $amount = (int)round($p['price'] * $mult);
    $sub += $amount * $q;
    $f["line_items[$i][quantity]"] = $q;
    $f["line_items[$i][price_data][currency]"] = $cur;
    $f["line_items[$i][price_data][unit_amount]"] = $amount;
    $f["line_items[$i][price_data][product_data][name]"] = $p['name'];
    $i++;
}
$ship = (int)round($cfg['shipping'] * $mult);
if ($ship > 0) {
    $f["line_items[$i][quantity]"] = 1; $f["line_items[$i][price_data][currency]"] = $cur;
    $f["line_items[$i][price_data][unit_amount]"] = $ship; $f["line_items[$i][price_data][product_data][name]"] = 'Shipping'; $i++;
}
$tax = (int)round($sub * $cfg['tax'] / 100);
if ($tax > 0) {
    $f["line_items[$i][quantity]"] = 1; $f["line_items[$i][price_data][currency]"] = $cur;
    $f["line_items[$i][price_data][unit_amount]"] = $tax; $f["line_items[$i][price_data][product_data][name]"] = 'Tax'; $i++;
}
$host = isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : '';
$back = isset($in['back']) ? (string)$in['back'] : '';
$bh = parse_url($back, PHP_URL_HOST);
$bp = parse_url($back, PHP_URL_PORT);
if (!$bh || strcasecmp($bh . ($bp ? ':' . $bp : ''), $host) !== 0) { $back = (isset($_SERVER['HTTPS']) ? 'https://' : 'http://') . $host . '/'; }
$f['success_url'] = $back . (strpos($back, '?') === false ? '?' : '&') . 'paid=1';
$f['cancel_url'] = $back;
$api = isset($cfg['stripe_api']) ? $cfg['stripe_api'] : 'https://api.stripe.com';
$ch = curl_init($api . '/v1/checkout/sessions');
curl_setopt_array($ch, array(CURLOPT_POST => true, CURLOPT_POSTFIELDS => http_build_query($f), CURLOPT_RETURNTRANSFER => true,
    CURLOPT_USERPWD => $cfg['stripe_secret'] . ':', CURLOPT_TIMEOUT => 20));
$res = curl_exec($ch);
$code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);
$j = json_decode((string)$res, true);
if ($code >= 200 && $code < 300 && is_array($j) && !empty($j['url'])) { echo json_encode(array('url' => $j['url'])); exit; }
$msg = (is_array($j) && isset($j['error']['message'])) ? $j['error']['message'] : 'Stripe could not start the payment.';
sw_fail(502, $msg);
"""


def php_files(doc, kinds):
    if not ({"product", "productgrid", "cart"} & kinds):
        return {}
    s = doc.shop
    if s["provider"] != "stripe" or not s.get("stripe_secret", "").strip():
        return {}
    from .phpgen import _q
    prods = ",\n".join("        %s => array('name' => %s, 'price' => %s)" % (_q(p["id"]), _q(p["name"]), repr(round(float(p["price"]), 2)))
                       for p in active(doc))
    cfg = ("<?php\n// Private. Visitors cannot open this folder.\nreturn array(\n    'stripe_secret' => %s,\n    'currency' => %s,\n"
           "    'shipping' => %s,\n    'tax' => %s,\n    'products' => array(\n%s\n    )\n);\n"
           % (_q(s["stripe_secret"].strip()), _q(s["currency"]), repr(float(s.get("shipping") or 0)), repr(float(s.get("tax") or 0)), prods))
    return {"stripe-checkout.php": STRIPE_PHP, "shop-private/config.php": cfg,
            "shop-private/.htaccess": "Require all denied\n<IfModule !mod_authz_core.c>\nDeny from all\n</IfModule>\n",
            "shop-private/index.html": ""}


# -- bringing products in from a store ---------------------------------------------------------------
def _get(url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers=dict({"User-Agent": "WebPlus"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def import_shopify(domain, token, api_base=None):
    """Products from a Shopify store through its Storefront API (the token is the public Storefront one)."""
    domain = re.sub(r"^https?://", "", domain.strip()).strip("/")
    q = ("{products(first:100){edges{node{id title description featuredImage{url} "
         "variants(first:1){edges{node{id price{amount currencyCode}}}}}}}}")
    url = (api_base or "https://%s" % domain) + "/api/2024-10/graphql.json"
    j = _get(url, {"Content-Type": "application/json", "X-Shopify-Storefront-Access-Token": token.strip()},
             json.dumps({"query": q}).encode())
    if j.get("errors"):
        raise ValueError(j["errors"][0].get("message", "Shopify refused the request"))
    out, cur = [], None
    for e in j["data"]["products"]["edges"]:
        n = e["node"]
        v = (n["variants"]["edges"] or [{}])[0].get("node") or {}
        if not v:
            continue
        p = new_product(n["title"])
        p.update(price=float(v["price"]["amount"]), desc=strip_html(n.get("description")),
                 image_url=(n.get("featuredImage") or {}).get("url", ""),
                 shopify_variant=v["id"].rsplit("/", 1)[-1])
        cur = v["price"]["currencyCode"]
        out.append(p)
    return out, cur


def import_woocommerce(site):
    """Products from a WooCommerce store through its public Store API."""
    base = site.strip().rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base
    j = _get(base + "/wp-json/wc/store/v1/products?per_page=100")
    out, cur = [], None
    for n in j:
        pr = n.get("prices") or {}
        minor = int(pr.get("currency_minor_unit", 2))
        p = new_product(strip_html(n.get("name")))
        p.update(price=int(pr.get("price") or 0) / float(10 ** minor), woo_id=str(n["id"]),
                 desc=strip_html(n.get("short_description") or n.get("description")),
                 image_url=((n.get("images") or [{}])[0] or {}).get("src", ""))
        cur = pr.get("currency_code") or cur
        out.append(p)
    return out, cur


def fetch_image(doc, p, limit=6_000_000):
    """Save a product's web picture inside the site, so the finished shop does not depend on another site."""
    url = p.get("image_url", "")
    if not url.startswith("http"):
        return
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "WebPlus"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(limit + 1)
        if len(data) > limit:
            return
        name = re.sub(r"[^A-Za-z0-9._-]", "_", urllib.parse.urlparse(url).path.rsplit("/", 1)[-1]) or "product.jpg"
        if "." not in name:
            name += ".jpg"
        p["asset"] = doc.add_asset_bytes(name, data)
        p["image_url"] = ""
    except (urllib.error.URLError, OSError, ValueError):
        pass


CSV_FIELDS = ["name", "price", "description", "image_url", "sku", "shopify_variant", "woo_id", "stripe_link"]


def products_to_csv(products):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(CSV_FIELDS)
    for p in products:
        w.writerow([p["name"], p["price"], p.get("desc", ""), p.get("image_url", ""), p.get("sku", ""),
                    p.get("shopify_variant", ""), p.get("woo_id", ""), p.get("stripe_link", "")])
    return out.getvalue()


def products_from_csv(text):
    out = []
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return out
    head = [h.strip().lower() for h in rows[0]]
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        row = {head[i]: r[i].strip() for i in range(min(len(head), len(r)))}
        if not row.get("name"):
            continue
        p = new_product(row["name"])
        try:
            p["price"] = float(re.sub(r"[^0-9.\-]", "", row.get("price", "0")) or 0)
        except ValueError:
            p["price"] = 0.0
        p.update(desc=row.get("description", row.get("desc", "")), image_url=row.get("image_url", row.get("image", "")),
                 sku=row.get("sku", ""), shopify_variant=row.get("shopify_variant", ""), woo_id=row.get("woo_id", ""),
                 stripe_link=row.get("stripe_link", ""))
        out.append(p)
    return out


# -- registration -----------------------------------------------------------------------------------------
def pick_products(win):
    return [(p["name"], p["id"]) for p in win.doc.shop["products"]]


CARD_LOOK = [("accent", "Button and price colour", "colour", None), ("card", "Card background", "colour!", None),
             ("stroke", "Outline colour", "colour!", None), ("sw", "Outline width", "int", (0, 10)),
             ("radius", "Corner radius", "int", (0, 40)), ("font", "Font", "font", None),
             ("size", "Size (px)", "int", (8, 40)), ("color", "Text colour", "colour", None)]

GRID = dict(DEFAULT_CARD, w=860, h=360, cols=3, card_h=330, btn="Add to cart")
GRID.pop("product")
CART = dict(dict(TEXT_BASE, size=15, bold=True, color="#ffffff"), w=190, h=44, label="Cart", accent="#1f3a5f", radius=8, link="")


def _on_insert_product(win, d):
    if not win.doc.shop["products"]:
        from . import shopdialog
        shopdialog.shop_manager(win)
    if win.doc.shop["products"] and not d.get("product"):
        d["product"] = win.doc.shop["products"][0]["id"]


KINDS = {
    "product": dict(name="Product", defaults=DEFAULT_CARD, on_insert=_on_insert_product, paint=paint_product,
                    export=export_product,
                    schema=[("Product", [("product", "Which product", "pick", pick_products),
                                         ("btn", "Button words", "text", None),
                                         ("show_image", "Show the picture", "bool", None),
                                         ("show_desc", "Show the description", "bool", None),
                                         ("buy_now", "Go straight to checkout", "bool", None)]),
                            ("Look", CARD_LOOK)]),
    "productgrid": dict(name="Product grid", defaults=GRID, paint=paint_grid, export=export_grid,
                        schema=[("Products", [("cols", "Products across", "int", (1, 6)),
                                              ("card_h", "Height of each card", "int", (150, 900)),
                                              ("btn", "Button words", "text", None),
                                              ("show_image", "Show the pictures", "bool", None),
                                              ("show_desc", "Show the descriptions", "bool", None),
                                              ("buy_now", "Go straight to checkout", "bool", None)]),
                                ("Look", CARD_LOOK)]),
    "cart": dict(name="Shopping cart", defaults=CART, paint=paint_cart, export=export_cart,
                 schema=[("Cart", [("label", "Name on the button", "text", None), ("accent", "Colour", "colour", None),
                                   ("color", "Text colour", "colour", None), ("radius", "Corner radius", "int", (0, 40)),
                                   ("font", "Font", "font", None), ("size", "Size (px)", "int", (8, 40))])]),
}
