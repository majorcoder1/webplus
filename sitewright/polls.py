"""Web polls: a question with choices, votes counted on your own PHP host, results as bars."""
import json
import re

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QPen

from .basics import TEXT_BASE
from .webapps import esc

DEFAULTS = dict(w=360, h=270, question="What is your favourite?", options="Option one\nOption two\nOption three",
                multi=False, results="after", btn="Vote", thanks="Thanks for voting!", closed=False,
                fill="#ffffff", stroke="#d0d7e2", sw=1, radius=8, bar="#2b7de9", link="",
                **dict(TEXT_BASE, size=15))

SCHEMA = [("Poll", [("question", "Question", "text", None),
                    ("options", "Choices (one per line)", "multi", None),
                    ("multi", "Allow more than one choice", "bool", None),
                    ("results", "Show the results", "choice", ["after", "always", "never"]),
                    ("btn", "Button words", "text", None),
                    ("thanks", "Thank-you message", "text", None),
                    ("closed", "Voting is closed (show the results only)", "bool", None)]),
          ("Look", [("fill", "Background", "colour!", None), ("stroke", "Outline colour", "colour!", None),
                    ("sw", "Outline width", "int", (0, 20)), ("radius", "Corner radius", "int", (0, 80)),
                    ("bar", "Result bar colour", "colour", None), ("font", "Font", "font", None),
                    ("size", "Size (px)", "int", (8, 60)), ("color", "Text colour", "colour", None)])]


def choices(d):
    return [o.strip() for o in (d.get("options") or "").splitlines() if o.strip()][:20]


def key(d):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(d.get("id", "x")))[:40] or "x"


def paint(p, r, d, win):
    p.setBrush(QColor(d["fill"]) if d.get("fill") else Qt.NoBrush)
    p.setPen(QPen(QColor(d["stroke"]), d.get("sw", 1)) if d.get("stroke") and d.get("sw") else Qt.NoPen)
    p.drawRoundedRect(r.adjusted(.5, .5, -.5, -.5), d.get("radius", 8), d.get("radius", 8))
    f = QFont(d.get("font", "Sans Serif"))
    f.setPixelSize(int(d.get("size", 15)))
    fb = QFont(f)
    fb.setBold(True)
    p.setFont(fb)
    p.setPen(QColor(d.get("color", "#222")))
    pad = 14
    top = r.top() + pad
    qh = f.pixelSize() * 2.4
    p.drawText(QRectF(r.left() + pad, top, r.width() - 2 * pad, qh), int(Qt.AlignLeft | Qt.TextWordWrap),
               d.get("question", ""))
    y = top + qh + 4
    p.setFont(f)
    opts = choices(d) or ["(add choices)"]
    row = f.pixelSize() * 1.9
    for i, o in enumerate(opts):
        if y + row > r.bottom() - 44:
            break
        shown = d.get("results") == "always" or d.get("closed")
        if shown:
            frac = [0.55, 0.3, 0.15, 0.1][i % 4]
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(d.get("bar", "#2b7de9")).lighter(170))
            p.drawRoundedRect(QRectF(r.left() + pad, y, (r.width() - 2 * pad) * frac, row - 4), 3, 3)
        else:
            p.setPen(QPen(QColor("#8a929c"), 1.3))
            p.setBrush(Qt.NoBrush)
            if d.get("multi"):
                p.drawRect(QRectF(r.left() + pad, y + row / 2 - 8, 14, 14))
            else:
                p.drawEllipse(QPointF(r.left() + pad + 7, y + row / 2 - 1), 7, 7)
        p.setPen(QColor(d.get("color", "#222")))
        p.drawText(QRectF(r.left() + pad + (6 if shown else 24), y, r.width() - 2 * pad - 8, row - 4),
                   int(Qt.AlignLeft | Qt.AlignVCenter), o)
        y += row
    if not d.get("closed"):
        bw = max(90, len(d.get("btn", "")) * 11 + 30)
        br = QRectF(r.left() + pad, r.bottom() - 38, bw, 28)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(d.get("bar", "#2b7de9")))
        p.drawRoundedRect(br, 5, 5)
        p.setPen(QColor("#ffffff"))
        p.drawText(br, int(Qt.AlignCenter), d.get("btn", "Vote"))


POLL_JS = """<script>
(function(){
var root=document.getElementById(__ID__),pid=__PID__,api=__API__,mode=__MODE__,closed=__CLOSED__,multi=__MULTI__;
if(!root)return;
var box=root.querySelector('.pl-opts'),msg=root.querySelector('.pl-msg'),btn=root.querySelector('.pl-btn');
var labels=[].slice.call(box.querySelectorAll('label'));
function bars(data,voted){
  var total=data.total||0;
  labels.forEach(function(l,i){
    var n=data.counts[i]||0,pc=total?Math.round(n*100/total):0;
    var b=l.querySelector('.pl-bar');
    if(!b){b=document.createElement('span');b.className='pl-bar';l.appendChild(b);}
    b.style.width=pc+'%';
    var t=l.querySelector('.pl-pc');
    if(!t){t=document.createElement('span');t.className='pl-pc';l.appendChild(t);}
    t.textContent=pc+'% ('+n+')';
    l.classList.add('pl-res');
  });
  msg.textContent=total+(total===1?' vote':' votes');
}
function lock(){[].slice.call(box.querySelectorAll('input')).forEach(function(i){i.disabled=true;});btn.style.display='none';}
function show(data,voted){
  if(closed){lock();bars(data,voted);return;}
  if(voted){lock();if(mode!=='never')bars(data,voted);else msg.textContent=__THANKS__;return;}
  if(mode==='always')bars(data,voted);
}
function get(cb){
  fetch(api+'?id='+encodeURIComponent(pid),{cache:'no-store'}).then(function(r){return r.json();}).then(cb)
   .catch(function(){msg.textContent='Voting needs a web host that runs PHP.';btn.disabled=true;});
}
get(function(d){if(d.error){msg.textContent=d.error;return;}show(d,d.voted);});
btn.addEventListener('click',function(){
  var sel=[];[].slice.call(box.querySelectorAll('input')).forEach(function(i,k){if(i.checked)sel.push(k);});
  if(!sel.length){msg.textContent='Choose an answer first.';return;}
  btn.disabled=true;
  var fd=new FormData();fd.append('id',pid);sel.forEach(function(k){fd.append('c[]',k);});
  fetch(api,{method:'POST',body:fd}).then(function(r){return r.json();}).then(function(d){
    btn.disabled=false;
    if(d.error&&!d.counts){msg.textContent=d.error;return;}
    lock();
    if(mode==='never'){msg.textContent=__THANKS__;}else{bars(d,true);}
  }).catch(function(){btn.disabled=false;msg.textContent='The vote could not be sent.';});
});
})();
</script>"""

POLL_CSS = (".pl{box-sizing:border-box;padding:14px;overflow:auto}"
            ".pl .pl-q{font-weight:bold;margin-bottom:10px}"
            ".pl label{display:block;position:relative;margin:6px 0;padding:6px 8px;border-radius:4px;overflow:hidden;cursor:pointer}"
            ".pl label input{margin-right:8px}"
            ".pl .pl-bar{position:absolute;left:0;top:0;bottom:0;background:var(--plc,#2b7de9);opacity:.22;z-index:0;transition:width .4s}"
            ".pl .pl-pc{position:absolute;right:8px;top:6px;font-size:.85em;opacity:.8}"
            ".pl label>*{position:relative;z-index:1}.pl .pl-bar{z-index:0}"
            ".pl .pl-btn{margin-top:8px;padding:7px 18px;border:0;border-radius:5px;color:#fff;background:var(--plc,#2b7de9);"
            "font:inherit;cursor:pointer}.pl .pl-btn:disabled{opacity:.6}"
            ".pl .pl-msg{margin-top:8px;font-size:.9em;opacity:.8}")


def export(d, css, files, anames, doc, tag, attr):
    from . import extras
    from .extras import text_css
    ids = "pl-" + key(d)
    opts = choices(d)
    kind = "checkbox" if d.get("multi") else "radio"
    labels = "".join('<label><input type="%s" name="%s" value="%d"><span>%s</span></label>' % (kind, ids, i, esc(o))
                     for i, o in enumerate(opts))
    extras.CONTEXT["scripts"].append(
        POLL_JS.replace("__ID__", json.dumps(ids)).replace("__PID__", json.dumps(key(d)))
        .replace("__API__", json.dumps(extras.CONTEXT.get("prefix", "") + "poll.php"))
        .replace("__MODE__", json.dumps(d.get("results", "after")))
        .replace("__CLOSED__", "true" if d.get("closed") else "false")
        .replace("__MULTI__", "true" if d.get("multi") else "false")
        .replace("__THANKS__", json.dumps(d.get("thanks", ""))))
    from .export import _page_css
    if POLL_CSS not in _page_css:
        _page_css.append(POLL_CSS)
    bg = "background:%s;" % d["fill"] if d.get("fill") else ""
    border = "border:%dpx solid %s;" % (d["sw"], d["stroke"]) if d.get("stroke") and d.get("sw") else ""
    return ('<div class="o pl" id="%s" style="%s;%s%sborder-radius:%dpx;--plc:%s;%s">'
            '<div class="pl-q">%s</div><div class="pl-opts">%s</div>'
            '<button type="button" class="pl-btn">%s</button><div class="pl-msg"></div></div>'
            % (ids, css, bg, border, d.get("radius", 8), d.get("bar", "#2b7de9"), text_css(d),
               esc(d.get("question", "")), labels, esc(d.get("btn", "Vote"))))


POLL_PHP = r"""<?php
// Web polls: counts the votes. Data is kept in poll-data/ (closed to visitors).
header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
$POLLS = array(
%(polls)s
);
$dir = __DIR__ . '/poll-data';
if (!is_dir($dir)) { @mkdir($dir, 0755, true); }
if (!file_exists($dir . '/.htaccess')) {
    @file_put_contents($dir . '/.htaccess', "Require all denied\n<IfModule !mod_authz_core.c>\nDeny from all\n</IfModule>\n");
    @file_put_contents($dir . '/index.html', '');
}
$id = isset($_REQUEST['id']) ? preg_replace('/[^A-Za-z0-9_-]/', '', (string)$_REQUEST['id']) : '';
if (!isset($POLLS[$id])) { http_response_code(404); echo '{"error":"This poll was not found."}'; exit; }
$poll = $POLLS[$id];
$file = $dir . '/' . $id . '.json';
$secret = hash('sha256', __FILE__ . php_uname('n'));
$ip = isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '';
$who = substr(hash('sha256', $ip . $secret . $id), 0, 20);
$cookie = 'swp_' . $id;

function sw_read($file, $n) {
    $d = array('counts' => array_fill(0, $n, 0), 'ips' => array());
    if (is_file($file)) {
        $j = json_decode((string)@file_get_contents($file), true);
        if (is_array($j) && isset($j['counts'])) { $d = $j; }
    }
    return $d;
}
function sw_out($d, $voted) {
    $total = array_sum($d['counts']);
    echo json_encode(array('counts' => array_values($d['counts']), 'total' => $total, 'voted' => $voted));
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if ($poll['closed']) { http_response_code(403); echo '{"error":"Voting is closed."}'; exit; }
    $c = isset($_POST['c']) && is_array($_POST['c']) ? array_values(array_unique(array_map('intval', $_POST['c']))) : array();
    if (!$c || (!$poll['multi'] && count($c) > 1) || count($c) > $poll['n']) { http_response_code(400); echo '{"error":"Choose a valid answer."}'; exit; }
    foreach ($c as $k) { if ($k < 0 || $k >= $poll['n']) { http_response_code(400); echo '{"error":"Choose a valid answer."}'; exit; } }
    $fh = fopen($file, 'c+');
    if (!$fh) { http_response_code(500); echo '{"error":"The vote could not be saved."}'; exit; }
    flock($fh, LOCK_EX);
    $raw = stream_get_contents($fh);
    $d = array('counts' => array_fill(0, $poll['n'], 0), 'ips' => array());
    $j = json_decode((string)$raw, true);
    if (is_array($j) && isset($j['counts'])) { $d = $j; }
    if (isset($_COOKIE[$cookie]) || in_array($who, $d['ips'], true)) {
        flock($fh, LOCK_UN); fclose($fh);
        http_response_code(409);
        $r = $d; $r['error'] = 'You have already voted.';
        $total = array_sum($d['counts']);
        echo json_encode(array('error' => 'You have already voted.', 'counts' => array_values($d['counts']), 'total' => $total, 'voted' => true));
        exit;
    }
    foreach ($c as $k) { $d['counts'][$k] = (isset($d['counts'][$k]) ? $d['counts'][$k] : 0) + 1; }
    $d['ips'][] = $who;
    if (count($d['ips']) > 5000) { $d['ips'] = array_slice($d['ips'], -5000); }
    ftruncate($fh, 0); rewind($fh);
    fwrite($fh, json_encode($d));
    fflush($fh);
    flock($fh, LOCK_UN); fclose($fh);
    setcookie($cookie, '1', time() + 31536000, '/');
    sw_out($d, true);
    exit;
}
$d = sw_read($file, $poll['n']);
sw_out($d, isset($_COOKIE[$cookie]) || in_array($who, $d['ips'], true));
"""


def php_files(doc, kinds):
    if "poll" not in kinds:
        return {}
    from .webapps import all_items
    rows = []
    for it in all_items(doc):
        if it["kind"] == "poll":
            rows.append("    '%s' => array('n' => %d, 'multi' => %s, 'closed' => %s)," % (
                key(it), max(len(choices(it)), 1), "true" if it.get("multi") else "false",
                "true" if it.get("closed") else "false"))
    return {"poll.php": POLL_PHP % {"polls": "\n".join(rows)}}


KINDS = {"poll": dict(name="Web poll", defaults=DEFAULTS, schema=SCHEMA, paint=paint, export=export)}
