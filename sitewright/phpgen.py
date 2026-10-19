"""The small PHP files WebPlus writes for member pages and the mailing list."""
import hashlib
import secrets

ITER = 100000


def hash_password(password, salt=None):
    """(salt, hex hash). Only these are kept - never the password itself."""
    salt = salt or secrets.token_hex(8)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), ITER)
    return salt, h.hex()


def _q(s):
    return "'" + str(s).replace("\\", "\\\\").replace("'", "\\'") + "'"


AUTH = r"""<?php
// Member sign-in for protected pages. Edit the members in the WebPlus program, not here.
if (!function_exists('sw_user')) {
function sw_members() {
    return array(
%(members)s
    );
}
function sw_start() {
    if (session_status() !== PHP_SESSION_ACTIVE) {
        if (PHP_VERSION_ID >= 70300) {
            session_set_cookie_params(array('httponly' => true, 'samesite' => 'Lax'));
        }
        session_start();
    }
}
function sw_user() {
    sw_start();
    return isset($_SESSION['sw_user']) ? $_SESSION['sw_user'] : null;
}
function sw_check($name, $password) {
    $m = sw_members();
    if (!isset($m[$name])) { return false; }
    $calc = hash_pbkdf2('sha256', (string)$password, $m[$name][0], %(iter)d, 64, false);
    return hash_equals($m[$name][1], $calc);
}
function sw_safe_return($r) {
    $r = (string)$r;
    if ($r === '' || $r[0] !== '/' || strpos($r, '//') === 0 || strpos($r, '://') !== false
        || strpos($r, "\n") !== false || strpos($r, "\r") !== false) { return '/'; }
    return $r;
}
function sw_login_page($up, $title, $message) {
    $action = htmlspecialchars($up . 'sw-auth.php', ENT_QUOTES);
    $ret = htmlspecialchars(sw_safe_return(isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : '/'), ENT_QUOTES);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8">'
       . '<meta name="viewport" content="width=device-width, initial-scale=1">'
       . '<meta name="robots" content="noindex,nofollow"><title>Members only - ' . htmlspecialchars($title) . '</title>'
       . '<style>body{font:16px sans-serif;background:#f3f5f8;display:flex;min-height:100vh;'
       . 'align-items:center;justify-content:center;margin:0}form{background:#fff;padding:28px;'
       . 'border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.15);width:min(92vw,340px)}'
       . 'input{display:block;width:100%%;box-sizing:border-box;padding:10px;margin:8px 0 14px;'
       . 'font-size:16px}button{width:100%%;padding:11px;font-size:16px;background:#2b7de9;color:#fff;'
       . 'border:0;border-radius:5px}p.e{color:#b3261e}</style></head><body>'
       . '<form method="post" action="' . $action . '"><h2>Members only</h2>'
       . ($message ? '<p class="e">' . htmlspecialchars($message) . '</p>' : '<p>Please sign in to see this page.</p>')
       . '<input type="hidden" name="action" value="login"><input type="hidden" name="return" value="' . $ret . '">'
       . '<label>User name<input name="user" autocomplete="username" required></label>'
       . '<label>Password<input type="password" name="pass" autocomplete="current-password" required></label>'
       . '<button type="submit">Sign in</button></form></body></html>';
}
function sw_require($up, $allowed, $title) {
    $u = sw_user();
    if ($u !== null && (count($allowed) === 0 || in_array($u, $allowed, true))) { return; }
    header('Cache-Control: no-store');
    if ($u !== null) { sw_login_page($up, $title, 'Your account may not view this page.'); }
    else { sw_login_page($up, $title, ''); }
    exit;
}
}
if (basename(isset($_SERVER['SCRIPT_FILENAME']) ? $_SERVER['SCRIPT_FILENAME'] : '') === 'sw-auth.php') {
    sw_start();
    $act = isset($_POST['action']) ? $_POST['action'] : (isset($_GET['action']) ? $_GET['action'] : '');
    $back = sw_safe_return(isset($_POST['return']) ? $_POST['return'] : (isset($_GET['return']) ? $_GET['return'] : '/'));
    if ($act === 'logout') {
        $_SESSION = array();
        session_destroy();
        header('Location: ' . $back);
        exit;
    }
    if ($act === 'login' && $_SERVER['REQUEST_METHOD'] === 'POST') {
        $fails = isset($_SESSION['sw_fail']) ? $_SESSION['sw_fail'] : array(0, 0);
        if ($fails[0] >= 5 && time() - $fails[1] < 60) {
            http_response_code(429);
            exit('Too many attempts. Please wait a minute and try again.');
        }
        $name = isset($_POST['user']) ? (string)$_POST['user'] : '';
        if (sw_check($name, isset($_POST['pass']) ? $_POST['pass'] : '')) {
            session_regenerate_id(true);
            $_SESSION['sw_user'] = $name;
            $_SESSION['sw_fail'] = array(0, 0);
            header('Location: ' . $back);
            exit;
        }
        $_SESSION['sw_fail'] = array($fails[0] + 1, time());
        sleep(1);
        sw_login_page('', %(title)s, 'That name or password was not right.');
        exit;
    }
    header('Location: /');
}
"""


def auth_php(members, title):
    rows = ",\n".join("        %s => array(%s, %s)" % (_q(m["name"]), _q(m["salt"]), _q(m["hash"]))
                      for m in members)
    return AUTH % dict(members=rows, iter=ITER, title=_q(title))


SUBSCRIBE = r"""<?php
// Mailing list sign-up.
$dir = __DIR__ . '/sw-data';
$file = $dir . '/list-%(token)s.csv';
$notify = %(notify)s;
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { header('Location: /'); exit; }
if (!is_dir($dir)) {
    @mkdir($dir, 0755, true);
    @file_put_contents($dir . '/.htaccess', "Require all denied\nDeny from all\n");
    @file_put_contents($dir . '/index.html', '');
}
$back = isset($_SERVER['HTTP_REFERER']) ? $_SERVER['HTTP_REFERER'] : '/';
$bh = parse_url($back, PHP_URL_HOST);
if ($bh && isset($_SERVER['HTTP_HOST']) && strcasecmp($bh, preg_replace('/:\d+$/', '', $_SERVER['HTTP_HOST'])) !== 0) { $back = '/'; }
$back = preg_replace('/([?&])joined=\d/', '', $back);
$sep = strpos($back, '?') === false ? '?' : '&';
if (!empty($_POST['website'])) { header('Location: ' . $back); exit; }       // spam trap
$email = isset($_POST['email']) ? trim($_POST['email']) : '';
if (!filter_var($email, FILTER_VALIDATE_EMAIL) || strlen($email) > 200) {
    header('Location: ' . $back . $sep . 'joined=0'); exit;
}
$line = date('Y-m-d H:i:s') . ',' . str_replace(array(',', "\n", "\r"), ' ', $email) . "\n";
$have = is_file($file) ? file_get_contents($file) : '';
if (stripos($have, ',' . $email . "\n") === false) {
    file_put_contents($file, $line, FILE_APPEND | LOCK_EX);
    if ($notify !== '') {
        @mail($notify, 'New mailing list sign-up', "New subscriber: " . $email);
    }
}
header('Location: ' . $back . $sep . 'joined=1');
"""

SUBSCRIBERS = r"""<?php
// Subscriber list - open this page with your secret key.
$key = %(key)s;
$file = __DIR__ . '/sw-data/list-%(token)s.csv';
header('Content-Type: text/html; charset=utf-8');
header('X-Robots-Tag: noindex');
if (!isset($_GET['key']) || !hash_equals($key, (string)$_GET['key'])) { http_response_code(403); exit('Not allowed.'); }
$rows = is_file($file) ? file($file, FILE_IGNORE_NEW_LINES) : array();
if (isset($_GET['csv'])) {
    header('Content-Type: text/csv');
    header('Content-Disposition: attachment; filename="subscribers.csv"');
    echo "date,email\n" . implode("\n", $rows) . "\n";
    exit;
}
echo '<!doctype html><meta charset="utf-8"><title>Subscribers</title>'
   . '<body style="font:16px sans-serif;margin:30px"><h1>' . count($rows) . ' subscriber(s)</h1>'
   . '<p><a href="?key=' . htmlspecialchars(urlencode($key)) . '&csv=1">Download as a spreadsheet file</a></p><table cellpadding="6">';
foreach (array_reverse($rows) as $r) {
    $p = explode(',', $r, 2);
    echo '<tr><td>' . htmlspecialchars($p[0]) . '</td><td>' . htmlspecialchars(isset($p[1]) ? $p[1] : '') . '</td></tr>';
}
echo '</table></body>';
"""


def subscribe_php(token, notify):
    return SUBSCRIBE % dict(token=token, notify=_q(notify or ""))


def subscribers_php(token, key):
    return SUBSCRIBERS % dict(token=token, key=_q(key))


def list_token(key):
    """A stable, unguessable file name part derived from the secret key."""
    return hashlib.sha256(("list|" + key).encode()).hexdigest()[:20]
