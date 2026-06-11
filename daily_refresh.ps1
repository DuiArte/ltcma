<#
.SYNOPSIS
  LTCMA daily website refresh -- Windows-native, fired by Task Scheduler.

.DESCRIPTION
  Single-source-of-truth pipeline (migration 2026-06-10): the generators run
  natively on Windows Python inside THIS repo clone; no WSL involvement.
  Replaces the old two-clone flow (WSL build + thin host wrapper), which is
  retired -- see AI_PROCEDURES\WEBSITE_REFRESH_WINDOWS_MIGRATION.md.

  Flow:
    1. Verify clean tree (auto-clean generated docs/data leftovers), pull --rebase.
    2. Data refresh (best-effort): 08 signals, 09 priced-in, 10 regimes,
       20 regime tracker, 19 stock analysis.
    3. Site rebuild: 17 site, 23 strategies, 27 research notes, 25 stock picks,
       21 signals redirect, 18 portfolio, 26 real-numbers, 22 AI copies,
       24 backtests redirect.  (17 and 23 are load-bearing: failure aborts.)
    4. Mirror docs/ + data/ backup -> Documents\CarlosDuarteWebsite.
    5. Verify as-of stamps + no fxaANEL/fxaOS CSS regression.
    6. git add docs data; commit; push; live-verify GitHub Pages.
  Logs to C:\Users\carlo\Scripts\logs\website_refresh_<date>.log (same place
  as the retired wrapper, so log history stays in one folder).

.PARAMETER BuildOnly
  Build + verify but skip commit/push and the live check (local testing).

.PARAMETER DryRun
  Verify-only: pull, check python + deps + source files. No build, no push.

.NOTES
  Windows-native migration 2026-06-10 (Fable 5). Python deps: see
  requirements.txt (+ yfinance). PYTHONUTF8=1 is forced: the generators print
  Unicode and write UTF-8; default cp1252 console would crash them.
#>
[CmdletBinding()]
param([switch]$BuildOnly, [switch]$DryRun)

$ErrorActionPreference = 'Stop'

# ---- Config -----------------------------------------------------------------
$Repo    = Split-Path -Parent $MyInvocation.MyCommand.Path   # this script lives in the repo root
$Scripts = Join-Path $Repo 'scripts'
$Docs    = Join-Path $Repo 'docs'
$Backup  = 'C:\Users\carlo\Documents\CarlosDuarteWebsite'
$LogDir  = 'C:\Users\carlo\Scripts\logs'
$Today   = Get-Date -Format 'yyyy-MM-dd'
$LogFile = Join-Path $LogDir "website_refresh_$Today.log"
$Urls    = @(
    'https://duiarte.github.io/ltcma/index.html',
    'https://duiarte.github.io/ltcma/portfolio.html',
    'https://duiarte.github.io/ltcma/regime.html',
    'https://duiarte.github.io/ltcma/strategies.html',
    'https://duiarte.github.io/ltcma/research.html',
    'https://duiarte.github.io/ltcma/stocks.html'
)

# generators print Unicode and write UTF-8; force UTF-8 mode on Windows Python
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# ---- Logging ----------------------------------------------------------------
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force $LogDir | Out-Null }
function Log {
    param([string]$Msg, [string]$Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Msg
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}
function Fail {
    param([string]$Msg)
    Log $Msg 'ERROR'
    Log ("=== refresh FAILED ({0}s) ===" -f [math]::Round(((Get-Date)-$script:Start).TotalSeconds)) 'ERROR'
    exit 1
}
function Invoke-Native {
    param([scriptblock]$Script)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try { $out = & $Script 2>&1 | ForEach-Object { "$_" }; $code = $LASTEXITCODE }
    finally { $ErrorActionPreference = $prev }
    return [pscustomobject]@{ Code = $code; Text = ($out -join "`n") }
}
# Run one generator. Load-bearing steps abort the refresh; the rest warn-and-continue
# (same contract as the retired daily_refresh.sh chain).
function Run-Step {
    param([string]$Name, [switch]$LoadBearing)
    Log "-- $Name"
    $r = Invoke-Native { python (Join-Path $Scripts $Name) }
    if ($r.Code -ne 0) {
        $tail = ($r.Text -split "`n" | Select-Object -Last 12) -join "`n"
        if ($LoadBearing) { Fail "$Name FAILED (load-bearing):`n$tail" }
        Log "$Name failed (continuing):`n$tail" 'WARN'
    }
    return $r
}

$script:Start = Get-Date
$mode = if ($DryRun) {'DRY RUN'} elseif ($BuildOnly) {'BUILD ONLY'} else {'LIVE'}
Log "=== Windows-native refresh START ($mode) ==="

try {
    Set-Location $Repo

    # ---- 1. clean tree + pull ----------------------------------------------
    $r = Invoke-Native { git status --porcelain }
    if ($r.Code -ne 0) { Fail "git status failed: $($r.Text)" }
    if ($r.Text.Trim()) {
        $dirty = $r.Text.Trim() -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
        $nonGenerated = $dirty | Where-Object { $_ -notmatch '^(M|MM|\?\?)?\s*(docs/|data/)' }
        if ($nonGenerated) { Fail "Working tree DIRTY beyond generated artifacts:`n$($r.Text)" }
        (Invoke-Native { git checkout -- docs data }) | Out-Null
        (Invoke-Native { git clean -fd docs data }) | Out-Null
        Log ("Auto-cleaned {0} generated leftovers from a prior interrupted run." -f $dirty.Count) 'WARN'
    }
    $r = Invoke-Native { git pull --rebase origin main }
    if ($r.Code -ne 0) { Fail "git pull --rebase failed:`n$($r.Text)" }
    Log "Tree clean; pulled origin/main."

    # ---- DryRun: environment checks only ------------------------------------
    $r = Invoke-Native { python -c "import pandas,numpy,plotly,yfinance,openpyxl,markdown,requests;import paths;print('ENV OK',paths.ROOT)" }
    if ($r.Code -ne 0) { Fail "Python env check failed (deps missing?):`n$($r.Text)" }
    # guard: paths.ROOT must be THIS repo, never the stale C:\Users\carlo\LTCMA decoy
    Push-Location $Scripts
    $rootChk = (Invoke-Native { python -c "import paths;print(paths.ROOT)" }).Text.Trim()
    Pop-Location
    if ($rootChk -ne $Repo) { Fail "paths.ROOT resolves to '$rootChk', expected '$Repo'" }
    Log "Python env OK; paths.ROOT = $rootChk"
    if ($DryRun) {
        Log "=== DRY RUN OK ($([math]::Round(((Get-Date)-$script:Start).TotalSeconds))s) ==="
        exit 0
    }

    # ---- 2. data refresh (best-effort) ---------------------------------------
    Push-Location $Scripts
    Run-Step '08_fetch_signals.py'   | Out-Null
    Run-Step '09_priced_in.py'       | Out-Null
    Run-Step '10_regimes.py'         | Out-Null
    Run-Step '20_regime_tracker.py'  | Out-Null
    Run-Step '19_stock_analysis.py'  | Out-Null

    # ---- 3. site rebuild ------------------------------------------------------
    Run-Step '17_build_site.py'      -LoadBearing | Out-Null
    Run-Step '23_strategies.py'      -LoadBearing | Out-Null
    Run-Step '27_research_notes.py'  | Out-Null
    Run-Step '25_stock_picks.py'     | Out-Null
    Run-Step '21_stock_signals.py'   | Out-Null
    Run-Step '18_portfolio.py'       | Out-Null
    Run-Step '26_real_numbers_refresh.py' | Out-Null
    Run-Step '22_ai_copies.py'       | Out-Null
    Run-Step '24_backtests.py'       | Out-Null
    Pop-Location
    Log "Site rebuild complete."

    # ---- 4. mirror backup -----------------------------------------------------
    if (-not (Test-Path $Backup)) { New-Item -ItemType Directory -Force $Backup | Out-Null }
    Copy-Item -Path (Join-Path $Repo 'docs') -Destination $Backup -Recurse -Force
    Copy-Item -Path (Join-Path $Repo 'data') -Destination $Backup -Recurse -Force
    Log "Mirrored docs/ + data/ -> $Backup"

    # ---- 5. verify as-of stamps + CSS regression ------------------------------
    $Yesterday     = (Get-Date).AddDays(-1).ToString('yyyy-MM-dd')
    $YesterdayLong = (Get-Date).AddDays(-1).ToString('dd MMM yyyy')
    $TodayLong     = Get-Date -Format 'dd MMM yyyy'
    $MorningRun    = (Get-Date).Hour -lt 12
    $portfolio = Join-Path $Docs 'portfolio.html'
    $asof = Select-String -Path $portfolio -Pattern ("As of {0}" -f $Today) -SimpleMatch
    if (-not $asof -and $MorningRun) {
        $asof = Select-String -Path $portfolio -Pattern ("As of {0}" -f $Yesterday) -SimpleMatch
        if ($asof) { Log "portfolio.html as-of is $Yesterday (pre-noon run; latest US close) - accepted." }
    }
    if (-not $asof) {
        $haveAny = Select-String -Path $portfolio -Pattern 'As of' -SimpleMatch | Select-Object -First 1
        Fail ("portfolio.html as-of mismatch (today {0}). Found: {1}" -f $Today, ($haveAny.Line))
    }
    $regimeFile = Join-Path $Docs 'regime.html'
    $regAsof = Select-String -Path $regimeFile -Pattern ("As of {0}" -f $TodayLong) -SimpleMatch
    if (-not $regAsof -and $MorningRun) {
        $regAsof = Select-String -Path $regimeFile -Pattern ("As of {0}" -f $YesterdayLong) -SimpleMatch
    }
    if (-not $regAsof) {
        $haveReg = Select-String -Path $regimeFile -Pattern 'class="asof"' | Select-Object -First 1
        Fail ("regime.html as-of mismatch (today {0}). Found: {1}" -f $TodayLong, ($haveReg.Line))
    }
    $regression = Select-String -Path (Join-Path $Docs '*.html') -Pattern 'fxaANEL','fxaOS'
    if (($regression | Measure-Object).Count -gt 0) { Fail "CSS regression: fxaANEL/fxaOS found. Aborting." }
    Log "As-of + regression checks passed."

    if ($BuildOnly) {
        Log "=== BUILD ONLY OK ($([math]::Round(((Get-Date)-$script:Start).TotalSeconds))s) -- not committing ==="
        exit 0
    }

    # ---- 6. commit + push + live verify ---------------------------------------
    (Invoke-Native { git add docs data }) | Out-Null
    $staged = (Invoke-Native { git diff --cached --name-only }).Text.Trim()
    if (-not $staged) {
        Log "No changes to commit (pages already current)." 'WARN'
    } else {
        $msg = "chore: daily website refresh $Today (Windows-native Task Scheduler)"
        $r = Invoke-Native { git commit -m $msg }
        if ($r.Code -ne 0) { Fail "git commit failed: $($r.Text)" }
        $hash = (Invoke-Native { git rev-parse --short HEAD }).Text.Trim()
        $r = Invoke-Native { git push origin main }
        if ($r.Code -ne 0) { Fail "git push failed:`n$($r.Text)" }
        Log "Pushed $hash to origin/main."
        Log "COMMIT_HASH=$hash"
    }

    Log "Sleeping 60s for GitHub Pages..."
    Start-Sleep -Seconds 60
    foreach ($u in $Urls) {
        try {
            $resp = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 30
            $hasAsof = ($resp.Content -match ("As of {0}" -f [regex]::Escape($Today))) -or `
                       ($resp.Content -match ("As of {0}" -f [regex]::Escape($TodayLong)))
            Log ("LIVE {0} -> HTTP {1}; as-of-today={2}" -f $u, $resp.StatusCode, $hasAsof)
        } catch {
            Log ("LIVE check failed for {0}: {1}" -f $u, $_.Exception.Message) 'WARN'
        }
    }

    Log "=== refresh DONE ($([math]::Round(((Get-Date)-$script:Start).TotalSeconds))s) ==="
    exit 0
}
catch {
    Fail ("Unhandled: {0}`n{1}" -f $_.Exception.Message, $_.ScriptStackTrace)
}
