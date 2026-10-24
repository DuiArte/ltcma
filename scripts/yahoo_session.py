"""yahoo_session -- the ONE transport for every Yahoo request the site makes (2026-10-23).

WHY. yfinance 1.3.0 talks to Yahoo through curl_cffi `Session(impersonate="chrome")` unless it is
handed another session: a spoofed Chrome TLS fingerprint plus Chrome's headers. The fetch policy
(Market Intel / rotation, now site-wide) is one honest User-Agent, no impersonation, no proxies,
no retries on 401/403/410/429, no consent-form posting, and a blocked source is a recorded gap
plus an alert -- never a workaround. Carlos (2026-10-23) delegated the approach.

WHAT. yfinance insists on a curl_cffi Session (yfinance/data.py raises on anything else), so the
narrowest honest change is a curl_cffi Session WITHOUT impersonate/ja3/akamai/extra_fp, carrying
the research User-Agent. yfinance keeps doing all the parsing, so every DataFrame keeps its shape.
Importing this module installs four layers (idempotent):

  1. TRANSPORT GUARD  curl_cffi.requests.Session.request refuses (locally, nothing sent) any
                      *.yahoo.com request from a session that is not a HonestSession. Whatever a
                      future yfinance does internally, no browser-impersonating Yahoo request can
                      leave a process that imported this module; the worst case is a gap + alert.
  2. ONE SESSION      yfinance's process-wide YfData singleton gets SESSION, and YfData._set_session
                      swaps any other session for it. `yf.download(...)` WITHOUT session= builds
                      Session(impersonate="chrome") and installs it (yfinance/multi.py) -- e.g. the
                      private buy-the-dip loader 35_bt_replay.py imports cannot be edited.
  3. ONE REQUEST      YfData._make_request is replaced by the same request minus yfinance's
                      "HTTP >= 400 -> flip the cookie strategy (Yahoo's consent form) -> retry".
                      Cookie + crumb use only the basic flow (fc.yahoo.com + v1/test/getcrumb),
                      the one rotation/sic_universe.py uses. A getcrumb answer that is not a crumb
                      (empty, HTML, whitespace) is discarded -- never sent as crumb= -- and trips
                      the crumb breaker below.
  4. PROCESS COOKIE   yfinance's cookie cache is replaced by an in-process one: every process mints
                      its own A3 cookie (one fc.yahoo.com request) and never reads or writes the
                      on-disk jar. So the honest session never presents a cookie minted under the
                      Chrome fingerprint, and a cookie Yahoo has invalidated cannot cost the next
                      run its fundamentals. (The timezone cache stays shared: it is data, not
                      identity. It is opened once at import, in the importing thread -- see install().)

ENVIRONMENT. curl-impersonate (the libcurl inside curl_cffi) reads CURL_IMPERSONATE and
CURL_IMPERSONATE_HEADERS whenever it creates a handle and would then send a full Chrome TLS
fingerprint + Chrome headers from a session whose `impersonate` is None. Both are removed from
this process's environment at import, BEFORE the session is built (alert if either was set), and a
Yahoo request is refused if either reappears mid-run. (Checked 2026-10-23 against a local TLS echo
server: with CURL_IMPERSONATE=chrome131 set before Python starts, removing it here -- after
curl_cffi is loaded -- restores curl's own ClientHello and headers.)

POLICY ON THE WIRE (HonestSession.request):
  401 / 403 / 410 / 429  -> YahooBlocked, never retried. 403/410/429 (and a consent wall, and a
                            getcrumb answer saying "Too Many Requests") trip the process-wide
                            breaker: no further Yahoo request this run. A 401 from the auth flow
                            (fc.yahoo.com, getcrumb) or a crumb endpoint (quoteSummary / v7 quote /
                            fundamentals) trips the crumb breaker only: those are refused locally,
                            no further cookie/crumb traffic is sent, and chart bars (which need no
                            crumb) continue. A 401 anywhere else trips the process-wide breaker.
  500 / 502 / 503 / 504  -> transient: the same request (same crumb) is re-sent ONCE after
                            RESEND_DELAY s, at most RESEND_5XX_MAX times per process (yfinance's own
                            code re-sent every >= 400 once). Nothing else is ever re-sent.
  consent.yahoo.com / guce.yahoo.com -> never requested by this code (yfinance's consent-form
                            cookie strategy and its "accept consent" POST are removed). If Yahoo
                            ever redirects a request there, curl follows that one GET; the answer
                            is discarded as a consent wall (process-wide breaker + alert) and no
                            form is ever submitted.
  pacing                 -> one Yahoo request start per MIN_INTERVAL s per process, across all
                            threads (LTCMA_YAHOO_MIN_INTERVAL, default 0.25 = 4 requests/s; the
                            19 screener's ~1,600-request burst ran at ~25/s under the Chrome
                            session and has not been tried at that rate with this client).
                            Endpoints, calls and threads are unchanged.
  YahooBlocked subclasses yfinance's YFRateLimitError, so yfinance propagates it instead of
  swallowing it; every call site already turns a Yahoo failure into its outage fallback, and 19 /
  25 keep the committed page when a block or < 90% coverage would publish a partial table.
  Each block is printed to stderr and appended to <alert dir>/YAHOO_ALERT.txt
  (LTCMA_ALERT_DIR, default C:\\Users\\carlo\\Scripts\\logs when it exists; nothing on a runner).

    import yahoo_session as ys
    yf.download(tickers, ..., session=ys.SESSION)      # explicit at every call site
    yf.Ticker(t, session=ys.SESSION)

    python yahoo_session.py --selftest   # offline, nothing sent: layers + environment + repo scan
                                         # exit 0 OK, 1 FAILED (policy), 2 WARN (untested versions,
                                         # or CURL_IMPERSONATE* was set and had to be removed)
"""
import atexit
import os
import sys
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit

from curl_cffi import requests as _cc
import yfinance as yf
from yfinance.exceptions import YFException, YFRateLimitError

# Market Intel's research_user_agent (Trading_Index/market_intel/config_a.yaml), verbatim.
USER_AGENT = "Mozilla/5.0 (compatible; CarlosDuarteResearch/0.1; market-intel CMA fetcher)"

BLOCK_CODES = {401, 403, 410, 429}                    # fetch policy: never retried
STOP_CODES = {403, 410, 429}                          # ... and no further Yahoo request this run
RESEND_CODES = {500, 502, 503, 504}                   # transient: re-sent once (policy allows)
RESEND_DELAY = 1.0                                    # seconds before that one re-send
RESEND_5XX_MAX = 20                                   # re-sends per process; then returned as-is
CONSENT_HOSTS = ("consent.yahoo.com", "guce.yahoo.com")
CRUMB_PATHS = ("/v10/finance/quoteSummary", "/v7/finance/quote", "/v1/test/getcrumb",
               "/ws/fundamentals-timeseries")
COOKIE_HOST = "fc.yahoo.com"                          # yfinance's basic cookie source
GETCRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
FINGERPRINT_KW = ("impersonate", "ja3", "akamai", "extra_fp", "perk")
CURL_ENV = ("CURL_IMPERSONATE", "CURL_IMPERSONATE_HEADERS")   # read by curl-impersonate itself
TESTED_YFINANCE = ("1.3.0",)
TESTED_CURL_CFFI = ("0.15.0",)


def _min_interval():
    try:
        return max(float(os.environ.get("LTCMA_YAHOO_MIN_INTERVAL", "0.25")), 0.0)
    except ValueError:
        return 0.25


MIN_INTERVAL = _min_interval()


class YahooBlocked(YFRateLimitError):
    """Yahoo refused us, or the breaker refused locally. Never retried; a recorded gap."""

    def __init__(self, msg):
        YFException.__init__(self, msg)


def _is_yahoo(host):
    return host == "yahoo.com" or host.endswith(".yahoo.com")


def _is_auth(host, path):
    """Cookie/crumb flow or an endpoint that needs the crumb (the 'crumb side')."""
    return host == COOKIE_HOST or path.startswith(CRUMB_PATHS)


def _alert_dir():
    d = os.environ.get("LTCMA_ALERT_DIR")
    if d:
        return d
    d = r"C:\Users\carlo\Scripts\logs" if os.name == "nt" else "/mnt/c/Users/carlo/Scripts/logs"
    return d if os.path.isdir(d) else None


_LOCK = threading.Lock()
_STATE = {"stop": None, "crumb_stop": None, "refused": 0, "requests": 0, "resent_5xx": 0,
          "blocks": [], "curl_env_removed": []}
_QUIET = False                                        # --selftest: no alert-file writes


def _alert(msg):
    line = (f"{datetime.now():%Y-%m-%d %H:%M:%S} {os.path.basename(sys.argv[0] or 'python')}: "
            f"{msg}")
    print(f"!! YAHOO {msg}", file=sys.stderr, flush=True)
    d = None if _QUIET else _alert_dir()
    if d:
        try:
            with open(os.path.join(d, "YAHOO_ALERT.txt"), "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass


def alert(msg):
    """Record a Yahoo-caused gap (stderr + YAHOO_ALERT.txt), e.g. a page kept at its committed copy."""
    _alert(msg)


def _block(cause, method, url, stop_all):
    """Record a block. `cause` is an HTTP status (int) or a short description."""
    u = urlsplit(url)
    why = (f"HTTP {cause}" if isinstance(cause, int) else str(cause)) + \
        f" on {method} {u.hostname}{u.path}"
    with _LOCK:
        first = not _STATE["blocks"]
        _STATE["blocks"].append(why)
        if stop_all and not _STATE["stop"]:
            _STATE["stop"] = why
        elif not stop_all and not _STATE["crumb_stop"]:
            _STATE["crumb_stop"] = why
    scope = "no further Yahoo request this run" if stop_all else \
        "no further crumb-bearing Yahoo request this run (chart bars continue)"
    if first or stop_all:
        _alert(f"BLOCKED: {why}; not retried, {scope} (recorded gap; fetch policy)")
    return YahooBlocked(f"Yahoo {why}: not retried ({scope})")


def status():
    """Snapshot of this process's Yahoo traffic: requests sent, blocks, local refusals."""
    with _LOCK:
        return {k: (list(v) if isinstance(v, list) else v) for k, v in _STATE.items()}


def blocked():
    """The first block recorded in this process (process-wide or crumb-side), or None. A caller
    that publishes a table assembled from many Yahoo answers checks this before publishing."""
    with _LOCK:
        return _STATE["stop"] or _STATE["crumb_stop"]


@atexit.register
def _summary():
    s = status()
    if s["blocks"] or s["refused"]:
        _alert(f"SUMMARY: {s['requests']} request(s) sent, {len(s['blocks'])} blocked, "
               f"{s['refused']} refused locally "
               f"({s['stop'] or s['crumb_stop'] or 'non-honest session (layer 1)'})")
    if s["resent_5xx"]:
        print(f"!! YAHOO note: {s['resent_5xx']} transient 5xx answer(s) were re-sent once",
              file=sys.stderr, flush=True)


# ---------------------------------------------------------------- environment (curl-impersonate)
def _os_env_has(name):
    """Is `name` set in the OS-level environment block (what libcurl reads), not just os.environ?"""
    try:
        import ctypes
        if os.name == "nt":
            return ctypes.windll.kernel32.GetEnvironmentVariableW(name, None, 0) > 0
        libc = ctypes.CDLL(None)
        libc.getenv.restype = ctypes.c_char_p
        return libc.getenv(name.encode()) is not None
    except Exception:                                                   # noqa: BLE001
        return name in os.environ


def _remove_curl_env():
    """Remove CURL_IMPERSONATE* from os.environ AND the OS environment. Returns the names found."""
    found = []
    for k in CURL_ENV:
        if k in os.environ or _os_env_has(k):
            found.append(k)
            os.environ.pop(k, None)
            try:
                os.unsetenv(k)                    # also when it was set behind os.environ's back
            except (AttributeError, OSError):
                pass
    return found


_CURL_ENV_AT_IMPORT = _remove_curl_env()             # BEFORE any HonestSession handle exists
if _CURL_ENV_AT_IMPORT:
    _STATE["curl_env_removed"] = list(_CURL_ENV_AT_IMPORT)
    _alert(f"environment variable(s) {', '.join(_CURL_ENV_AT_IMPORT)} were set: curl would have "
           "sent a Chrome TLS fingerprint and Chrome headers from the honest session. Removed for "
           "this process before any Yahoo session was built; find and remove the setting.")


# ---------------------------------------------------------------- pacing + breaker gate
_PACE_LOCK = threading.Lock()
_PACE = {"next": 0.0}


def _pace():
    """One Yahoo request start per MIN_INTERVAL seconds in this process, whatever the threads."""
    if MIN_INTERVAL <= 0:
        return
    with _PACE_LOCK:
        now = time.perf_counter()                 # monotonic + sub-ms (monotonic(): ~16 ms on Windows)
        slot = max(now, _PACE["next"])
        _PACE["next"] = slot + MIN_INTERVAL
    if slot > now:
        time.sleep(slot - now)


def _gate(host, path, send):
    """Refuse locally after a block; count the request when `send`."""
    with _LOCK:
        stop = _STATE["stop"] or (_STATE["crumb_stop"] if _is_auth(host, path) else None)
        if stop:
            _STATE["refused"] += 1
        elif send:
            _STATE["requests"] += 1
    if stop:
        raise YahooBlocked(f"Yahoo request refused locally after an earlier block ({stop})")


def _resend_allowed():
    with _LOCK:
        if _STATE["stop"] or _STATE["resent_5xx"] >= RESEND_5XX_MAX:
            return False
        _STATE["resent_5xx"] += 1
        return True


# ---------------------------------------------------------------- the session
_ORIG_REQUEST = _cc.Session.request


class HonestSession(_cc.Session):
    """curl_cffi Session with no browser fingerprint: curl's own TLS ClientHello and headers,
    one honest User-Agent, no environment proxies, no curl-level retries."""

    def __init__(self):
        _remove_curl_env()                        # handles are created from here on
        kw = dict(headers={"User-Agent": USER_AGENT}, trust_env=False, timeout=30)
        try:
            super().__init__(retry=0, **kw)
        except TypeError:                         # curl_cffi without the `retry` option
            super().__init__(**kw)

    def _send(self, method, url, host, path, args, kw):
        _gate(host, path, send=False)             # refuse at once after a block (no pacing wait)
        _pace()
        _gate(host, path, send=True)              # re-check: another thread may have tripped it
        return _ORIG_REQUEST(self, method, url, *args, **kw)

    def request(self, method, url, *args, **kw):
        for k in FINGERPRINT_KW:
            if kw.get(k):
                raise ValueError(f"yahoo_session: refusing per-request {k}={kw[k]!r}")
        if any(getattr(self, k, None) for k in FINGERPRINT_KW):
            raise ValueError("yahoo_session: HonestSession was given a browser fingerprint")
        u = urlsplit(url)
        host, path = (u.hostname or "").lower(), u.path
        if host.endswith(CONSENT_HOSTS):
            raise YahooBlocked(f"Yahoo consent host {host}: never contacted (policy)")
        if not _is_yahoo(host):
            return _ORIG_REQUEST(self, method, url, *args, **kw)
        if any(k in os.environ for k in CURL_ENV):
            # set mid-run: a curl handle created since then would impersonate Chrome
            found = _remove_curl_env()
            raise _block(f"{'/'.join(found)} set mid-run (curl would impersonate a browser)",
                         method, url, stop_all=True)
        r = self._send(method, url, host, path, args, kw)
        if r.status_code in RESEND_CODES and _resend_allowed():
            print(f"!! YAHOO HTTP {r.status_code} on {method} {host}{path}: transient, re-sent "
                  f"once in {RESEND_DELAY:g}s", file=sys.stderr, flush=True)
            time.sleep(RESEND_DELAY)
            r = self._send(method, url, host, path, args, kw)
        final = (urlsplit(str(getattr(r, "url", "") or "")).hostname or "").lower()
        if final.endswith(CONSENT_HOSTS):
            raise _block(f"redirect to consent wall {final}", method, url, stop_all=True)
        if r.status_code in BLOCK_CODES:
            raise _block(r.status_code, method, url,
                         stop_all=r.status_code in STOP_CODES or not _is_auth(host, path))
        return r


SESSION = HonestSession()


# ---------------------------------------------------------------- yfinance hooks
def _guarded_request(self, method, url, *args, **kw):
    """Layer 1: Session.request for every curl_cffi Session in this process."""
    host = (urlsplit(url).hostname or "").lower()
    if _is_yahoo(host) and not isinstance(self, HonestSession):
        with _LOCK:
            _STATE["refused"] += 1
            first = _STATE["refused"] == 1
        if first:
            _alert(f"REFUSED: a non-honest curl_cffi session tried {host}{urlsplit(url).path} "
                   f"(impersonate={getattr(self, 'impersonate', None)!r}); nothing sent")
        raise YahooBlocked(f"non-honest session refused for {host} (yahoo_session layer 1)")
    return _ORIG_REQUEST(self, method, url, *args, **kw)


def _crumb_ok(c):
    """A real crumb is a short token: no markup, no whitespace (Yahoo's are ~11 characters)."""
    return isinstance(c, str) and 0 < len(c) <= 64 and "<" not in c and \
        not any(ch.isspace() for ch in c)


def _honest_crumb(self, timeout):
    """Basic cookie + crumb only (fc.yahoo.com + getcrumb); never the consent-form strategy.
    None when Yahoo will not give one: chart requests go without, crumb endpoints get a 401.
    After any block no cookie/crumb request is attempted again this run."""
    with _LOCK:
        if _STATE["stop"] or _STATE["crumb_stop"]:
            return None
    with self._cookie_lock:
        self._cookie_strategy = "basic"
        try:
            crumb = self._get_cookie_and_crumb_basic(timeout)
        except YahooBlocked:
            return None
        except YFRateLimitError:
            # getcrumb answered without a 429 status but with a "Too Many Requests" body
            # (yfinance's own check): a rate limit in all but name -> breaker, not a retry.
            self._crumb = None
            raise _block("getcrumb body 'Too Many Requests' (a 429 in all but status)", "GET",
                         GETCRUMB_URL, stop_all=True)
        if self._crumb is not None and not _crumb_ok(self._crumb):
            # e.g. a 200 "<html>...Will be right back" page: yfinance keeps it in _crumb and would
            # send it as crumb= on every later request. Drop it; crumb side stops for this run.
            self._crumb = None
            _block("getcrumb answer is not a crumb (empty/HTML body)", "GET", GETCRUMB_URL,
                   stop_all=False)
            return None
        return crumb


def _yf_retries():
    try:
        from yfinance.config import YfConfig
        return max(int(YfConfig.network.retries), 0)
    except Exception:                                                   # noqa: BLE001
        return 0


def _transient(e):
    try:
        from yfinance.data import _is_transient_error
        return bool(_is_transient_error(e))
    except Exception:                                                   # noqa: BLE001
        return False


def _honest_make_request(self, url, request_method, body=None, params=None, timeout=30,
                         data=None):
    """yfinance 1.3.0 YfData._make_request, minus the >=400 cookie-strategy flip + retry and the
    proxy sync (HonestSession never uses a proxy). yfinance's own network-error retry loop
    (YfConfig.network.retries, default 0) is kept as it was."""
    params = {} if params is None else params
    if "crumb" in params:
        raise YFException("Don't manually add 'crumb' to params dict, let data.py handle it")
    crumb = _honest_crumb(self, timeout)
    request_args = {"url": url, "params": {**params, **({"crumb": crumb} if crumb else {})},
                    "timeout": timeout}
    if body:
        request_args["json"] = body
    if data:
        request_args["data"] = data
        request_args["headers"] = {"Content-Type": "application/json"}
    retries = _yf_retries()
    for attempt in range(retries + 1):
        try:
            return request_method(**request_args)  # one request (+ one 5xx re-send); blocks raise
        except YahooBlocked:
            raise
        except Exception as e:                                          # noqa: BLE001
            if attempt < retries and _transient(e):
                time.sleep(2 ** attempt)
            else:
                raise


class _ProcessCookieCache:
    """Stand-in for yfinance's on-disk cookie cache (layer 4): lives and dies with this process."""

    def __init__(self):
        self._lock = threading.Lock()
        self._d = {}

    def lookup(self, strategy):
        with self._lock:
            v = self._d.get(strategy)
        return None if v is None else {"cookie": v[0], "age": datetime.now() - v[1]}

    def store(self, strategy, cookie):
        with self._lock:
            if cookie is None:
                self._d.pop(strategy, None)
            else:
                self._d[strategy] = (cookie, datetime.now())


_PROCESS_COOKIES = _ProcessCookieCache()
_INSTALLED = {}


def install():
    """Install the four layers. Idempotent. Returns {layer: True/False}."""
    if _INSTALLED:
        return dict(_INSTALLED)
    _cc.Session.request = _guarded_request                          # layer 1
    _INSTALLED["transport_guard"] = True
    try:
        from yfinance import data as _yd
        YfData = _yd.YfData
        need = ("_set_session", "_make_request", "_get_cookie_and_crumb_basic")
        if not all(hasattr(YfData, a) for a in need):
            raise AttributeError("YfData lacks " + ", ".join(a for a in need
                                                             if not hasattr(YfData, a)))
        _orig_set = YfData._set_session

        def _set_session(self, session):                            # layer 2
            if session is not None and not isinstance(session, HonestSession):
                session = SESSION
            return _orig_set(self, session)

        YfData._set_session = _set_session
        YfData(session=SESSION)
        _INSTALLED["one_session"] = True
        YfData._make_request = _honest_make_request                 # layer 3
        _INSTALLED["one_request"] = True
    except Exception as e:                                          # noqa: BLE001
        # Layer 1 still holds: nothing dishonest can leave, Yahoo just becomes a gap.
        _INSTALLED.setdefault("one_session", False)
        _INSTALLED.setdefault("one_request", False)
        _alert(f"yfinance {getattr(yf, '__version__', '?')} internals not as expected "
               f"({type(e).__name__}: {e}); Yahoo requests will be refused (gap)")
    try:                                                            # layer 4
        from yfinance import cache as _yc
        _yc._CookieCacheManager._Cookie_cache = _PROCESS_COOKIES
        _INSTALLED["process_cookie"] = _yc.get_cookie_cache() is _PROCESS_COOKIES
    except Exception:                                               # noqa: BLE001
        _INSTALLED["process_cookie"] = False
    try:
        # Open yfinance's timezone cache once, here, in the importing thread (local sqlite, no
        # network). Otherwise its first open happens inside yf.download's worker threads, which
        # race on sqlite's journal-mode switch ("database is locked" -> one ticker silently
        # dropped); seen in offline replays on a fresh cache, with and without this module.
        from yfinance import cache as _yc
        _yc.get_tz_cache().lookup("^GSPC")
        _INSTALLED["tz_cache_opened"] = True
    except Exception:                                               # noqa: BLE001
        _INSTALLED["tz_cache_opened"] = False
    return dict(_INSTALLED)


install()


# ---------------------------------------------------------------- self-test (offline)
FETCH_NAMES = {"download", "Ticker", "Tickers", "Search", "Lookup", "Sector", "Industry",
               "Market", "screen", "Calendars"}            # every yfinance entry that takes session=
UNCOVERED_NAMES = {"WebSocket", "AsyncWebSocket"}          # websockets library, not curl_cffi
SKIP_DIRS = {".git", "docs", "data", "report", "node_modules", "__pycache__", ".venv", "venv"}


def scan_source(src, name="<src>"):
    """Static check of one Python file (ast, not regex). Returns a list of problems:
    - imports yfinance (any form, incl. importlib/__import__) without `import yahoo_session`
    - a yfinance network entry point called without session=<yahoo_session>.SESSION
    - a yfinance entry point referenced without being called (aliased: cannot be checked)
    - the websocket streamer (not curl_cffi, so not covered by the honest transport)"""
    import ast
    try:
        tree = ast.parse(src, filename=name)
    except SyntaxError as e:
        return [f"{name}: cannot parse ({e.msg}, line {e.lineno}) but mentions yfinance"] \
            if "yfinance" in src else []
    yf_mods, yf_bare, ys_mods, ys_session = set(), {}, set(), set()
    imports_yf = dynamic = imports_ys = star = False
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name == "yfinance" or a.name.startswith("yfinance."):
                    imports_yf = True
                    yf_mods.add(a.asname or a.name.split(".")[0])
                elif a.name == "yahoo_session":
                    imports_ys = True
                    ys_mods.add(a.asname or a.name)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            if n.module == "yfinance" or n.module.startswith("yfinance."):
                imports_yf = True
                for a in n.names:
                    if a.name == "*":
                        star = True
                    yf_bare[a.asname or a.name] = a.name
            elif n.module == "yahoo_session":
                imports_ys = True
                for a in n.names:
                    if a.name == "SESSION":
                        ys_session.add(a.asname or a.name)
        elif isinstance(n, ast.Call):
            f = n.func
            fname = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if fname in ("import_module", "__import__") and n.args and \
                    isinstance(n.args[0], ast.Constant) and \
                    str(n.args[0].value).split(".")[0] == "yfinance":
                imports_yf = dynamic = True
    if not imports_yf:
        return []
    bad = []
    if not imports_ys:
        bad.append(f"{name}: imports yfinance without `import yahoo_session`")
    if dynamic:
        bad.append(f"{name}: imports yfinance dynamically (importlib/__import__): calls cannot be checked")
    if star:
        bad.append(f"{name}: `from yfinance import *`: calls cannot be checked")

    def _root(node):
        while isinstance(node, ast.Attribute):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None

    def _target(node):
        """'download' etc. when node is <yfinance alias>[.sub...].NAME or a bare imported NAME."""
        if isinstance(node, ast.Attribute) and _root(node) in yf_mods:
            return node.attr
        if isinstance(node, ast.Name) and node.id in yf_bare:
            return yf_bare[node.id]
        return None

    def _honest_kw(call):
        for k in call.keywords:
            if k.arg != "session":
                continue
            v = k.value
            if isinstance(v, ast.Attribute) and v.attr == "SESSION" and \
                    isinstance(v.value, ast.Name) and v.value.id in ys_mods:
                return True
            if isinstance(v, ast.Name) and v.id in ys_session:
                return True
        return False

    called = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            t = _target(n.func)
            if t:
                called.add(id(n.func))
                if t in FETCH_NAMES and not _honest_kw(n):
                    bad.append(f"{name}:{n.lineno}: yfinance {t}( without session=yahoo_session.SESSION")
    for n in ast.walk(tree):
        if isinstance(n, (ast.Attribute, ast.Name)) and isinstance(getattr(n, "ctx", None), ast.Load) \
                and id(n) not in called:
            t = _target(n)
            if t in UNCOVERED_NAMES:
                bad.append(f"{name}:{n.lineno}: yfinance {t} streams over websockets, outside the "
                           "honest transport")
            elif t in FETCH_NAMES:
                bad.append(f"{name}:{n.lineno}: yfinance {t} used without being called "
                           "(aliased; session= cannot be checked)")
    for n in ast.walk(tree):                     # bare `from yfinance import WebSocket` + call
        if isinstance(n, ast.Call) and _target(n.func) in UNCOVERED_NAMES:
            bad.append(f"{name}:{n.lineno}: yfinance {_target(n.func)} streams over websockets, "
                       "outside the honest transport")
    return bad


def scan_repo(root):
    """scan_source over every *.py under the repo (generated/output dirs skipped)."""
    bad = []
    here = os.path.abspath(__file__)
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in sorted(files):
            p = os.path.join(d, f)
            if not f.endswith(".py") or os.path.abspath(p) == here:
                continue
            try:
                src = open(p, encoding="utf-8-sig").read()     # a BOM is valid Python source
            except (OSError, UnicodeDecodeError) as e:
                bad.append(f"{os.path.relpath(p, root)}: unreadable ({e})")
                continue
            if "yfinance" in src:
                bad += scan_source(src, os.path.relpath(p, root).replace(os.sep, "/"))
    return bad


def _selftest():
    import curl_cffi
    from curl_cffi.const import CurlOpt
    from yfinance import cache as _yc, data as _yd
    global _QUIET
    _QUIET = True
    d = _yd.YfData()
    fail = {
        "layers installed": all(v for k, v in install().items() if k != "tz_cache_opened"),
        "singleton session is SESSION": d._session is SESSION,
        "SESSION has no impersonate/ja3/akamai/extra_fp": not (SESSION.impersonate or SESSION.ja3
                                                              or SESSION.akamai or SESSION.extra_fp),
        "SESSION User-Agent": SESSION.headers.get("User-Agent") == USER_AGENT,
        "SESSION trust_env False (no env proxies)": SESSION.trust_env is False,
        "CURL_IMPERSONATE / CURL_IMPERSONATE_HEADERS absent (os.environ and OS environment)":
            not any(k in os.environ or _os_env_has(k) for k in CURL_ENV),
        "yfinance cookie cache is process-only": _yc.get_cookie_cache() is _PROCESS_COOKIES,
    }
    # a chrome session handed to yfinance must be swapped back (no network)
    _yd.YfData(session=_cc.Session(impersonate="chrome"))
    fail["chrome session swapped for SESSION"] = _yd.YfData()._session is SESSION
    # the transport guard refuses a chrome session outright. The probe session is also pinned to
    # 127.0.0.1:9, so even a broken guard sends nothing off this machine (connection refused).
    probe = _cc.Session(impersonate="chrome", curl_options={CurlOpt.CONNECT_TO: ["::127.0.0.1:9"]},
                        timeout=5)
    with _LOCK:                                   # an expected refusal: no REFUSED alert line
        _STATE["refused"] = 1
    try:
        probe.get("https://query2.finance.yahoo.com/v8/finance/chart/SPY")
        fail["transport guard refuses chrome->yahoo"] = False
    except YahooBlocked:
        fail["transport guard refuses chrome->yahoo"] = True
    except Exception:                                                   # noqa: BLE001
        fail["transport guard refuses chrome->yahoo"] = False   # reached curl: guard bypassed
    with _LOCK:                                   # the guard test is not a real refusal
        _STATE["refused"] = 0
    warn = {
        f"yfinance version tested ({getattr(yf, '__version__', '?')} vs {'/'.join(TESTED_YFINANCE)})":
            getattr(yf, "__version__", "?") in TESTED_YFINANCE,
        f"curl_cffi version tested ({curl_cffi.__version__} vs {'/'.join(TESTED_CURL_CFFI)})":
            curl_cffi.__version__ in TESTED_CURL_CFFI,
        "CURL_IMPERSONATE* not set at start (" + (", ".join(_CURL_ENV_AT_IMPORT) or "none") +
        " removed at import)": not _CURL_ENV_AT_IMPORT,
    }
    for k, v in fail.items():
        print(f"  [{'ok' if v else 'FAIL'}] {k}")
    for k, v in warn.items():
        print(f"  [{'ok' if v else 'WARN'}] {k}")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = scan_repo(root)
    for b in bad:
        print(f"  [FAIL] {b}")
    print(f"  scanned {root} for yfinance use: {len(bad)} problem(s)")
    if bad or not all(fail.values()):
        print("SELFTEST FAILED")
        return 1
    if not all(warn.values()):
        print("SELFTEST WARN")
        return 2
    print("SELFTEST OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    print(__doc__)
