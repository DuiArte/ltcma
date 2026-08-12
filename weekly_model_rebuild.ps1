<#
.SYNOPSIS
  LTCMA WEEKLY full model rebuild -- Windows-native, fired by Task Scheduler
  Sundays 22:00 CDMX.  Companion to daily_refresh.ps1, which only re-renders the
  site over frozen model output.

.DESCRIPTION
  The daily refresh runs 08/09/10/17-28: signals and pages, never the model. So
  before 2026-08-11 the LTCMA core (01-04) and the Monte Carlo (06/07/11) only
  moved when a human deliberately ran them -- and they had drifted for MONTHS.
  This job closes that gap on a weekly cadence.  Why weekly: see
  AI_PROCEDURES\LTCMA_REBUILD.md, "Scheduling regime".

  Flow:
    1. Guard clean tree (generated docs/+data/ leftovers auto-cleaned), pull --rebase.
    2. Long history: 05a download, 05b parse (ASSERTS Shiller vintage freshness).
    3. LTCMA core: 01 prices+macro, 02 valuations, 03 model, 04 portfolios.
       ALL load-bearing -- a half-built model must never reach the gate.
    4. MATERIALITY GATE (scripts/model_delta_gate.py): rebuilt data/ vs HEAD.
       A breach reverts data/ and stops the run. Nothing is published.
    5. Risk + simulation: 06, 07, 11 -- ONE UNIT. If any fails (e.g. cupy), all
       three outputs are reverted to HEAD so the block keeps a single coherent
       vintage, and the run continues (the site stamps the MC vintage separately).
    6. Commit data/ ON ITS OWN (F6 rule: generated data never rides with source).
    7. Push the data commit. Rendering is left to the next daily refresh.

  WHY THIS JOB DOES NOT PUBLISH THE SITE (important -- do not "fix" this):
  daily_refresh.ps1 enforces a HARD "As of <today>" gate on portfolio.html and
  regime.html, and the broker snapshot those pages stamp only advances on a
  trading day. That is precisely why the daily task is registered Mon-Fri and why
  the watchdog answers "no refresh expected" at a weekend. A Sunday-night job that
  tried to rebuild docs/ would therefore trip the as-of gate and Fail() every week
  -- turning a healthy model refresh into a weekly false alarm.
  So the weekly job commits and pushes data/ ONLY. Monday's 16:31 daily refresh
  pulls it and renders the site over the fresh model, which is exactly the split
  of duties the two jobs already have. Pass -Publish to force the docs rebuild +
  push handoff, which is safe on a WEEKDAY (that is how the 2026-08-11 manual
  catch-up run published).

  Logs to C:\Users\carlo\Scripts\logs\model_rebuild_<date>.log.
  On failure writes C:\Users\carlo\Scripts\logs\MODEL_ALERT.txt (read by the
  same digests that read REFRESH_ALERT.txt).

.PARAMETER Force
  Publish even if the materiality gate reports a breach. Use only after a human
  has read the gate output and confirmed the move is real.

.PARAMETER SkipMC
  Skip 06/07/11 entirely (leaves the risk+simulation block at its current vintage).

.PARAMETER Publish
  After committing data/, also hand off to daily_refresh.ps1 to rebuild docs/,
  push and live-verify Pages. WEEKDAYS ONLY -- see the note above. The scheduled
  Sunday run deliberately does NOT pass this.

.PARAMETER BuildOnly
  Run the model and the gate, but do not commit, publish or push.

.PARAMETER DryRun
  Environment + guard checks only. No downloads, no build.

.NOTES
  Created 2026-08-11. ASCII-only by convention (cp1252 console eats curly quotes).
  PYTHONUTF8 is forced: the generators print Unicode and write UTF-8.
#>
[CmdletBinding()]
param([switch]$Force, [switch]$SkipMC, [switch]$Publish, [switch]$BuildOnly, [switch]$DryRun)

$ErrorActionPreference = 'Stop'

# ---- Config -----------------------------------------------------------------
$Repo    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Scripts = Join-Path $Repo 'scripts'
$LogDir  = 'C:\Users\carlo\Scripts\logs'
$Today   = Get-Date -Format 'yyyy-MM-dd'
$LogFile = Join-Path $LogDir "model_rebuild_$Today.log"
$AlertFile = Join-Path $LogDir 'MODEL_ALERT.txt'

# The risk + simulation block is atomic: 06 feeds 07 and 11, and publishing a new
# covariance against an old simulation silently desynchronises the two. If any of
# the three fails we revert ALL of these, so the block always carries one vintage.
$MCFiles = @(
    'data/ltcma_corr_v2.csv', 'data/ltcma_vol_v2.csv', 'data/ltcma_cov_v2.csv',
    'data/mc_assets.csv', 'data/mc_portfolios.csv',
    'data/mc_regime_assets.csv', 'data/mc_regime_portfolios.csv',
    'data/geopolitical_scenario.csv', 'data/mc_meta.json',
    'data/longhistory/damodaran_longrun.csv'
)

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
    Log ("=== model rebuild FAILED ({0}s) ===" -f [math]::Round(((Get-Date)-$script:Start).TotalSeconds)) 'ERROR'
    # A -DryRun / -BuildOnly failure is a TEST, not a production outage. Writing the
    # alert file for one leaves a stale alarm that nothing clears (a dry run exits
    # before the success path), and a false alert is worse than none -- it teaches
    # whoever reads it to ignore the file. Only a real scheduled run raises it.
    if ($DryRun -or $BuildOnly) { exit 1 }
    try {
        Set-Content -Path $AlertFile -Encoding utf8 -Value @"
$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') weekly model rebuild FAILED
$Msg
Log: $LogFile
Nothing was committed or pushed; the site is still on the last good model vintage.
"@
    } catch { }
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
function Run-Step {
    param([string]$Name, [switch]$LoadBearing)
    Log "-- $Name"
    $r = Invoke-Native { python (Join-Path $Scripts $Name) }
    if ($r.Code -ne 0) {
        $tail = ($r.Text -split "`n" | Select-Object -Last 15) -join "`n"
        if ($LoadBearing) { Fail "$Name FAILED (load-bearing):`n$tail" }
        Log "$Name failed (continuing):`n$tail" 'WARN'
    } else {
        $tail = ($r.Text -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 4) -join ' | '
        if ($tail) { Log "   $tail" }
    }
    return $r
}

$script:Start = Get-Date
$mode = if ($DryRun) {'DRY RUN'} elseif ($BuildOnly) {'BUILD ONLY'} else {'LIVE'}
Log "=== WEEKLY model rebuild START ($mode) ==="

try {
    Set-Location $Repo

    # ---- 1. clean tree + pull ------------------------------------------------
    $r = Invoke-Native { git status --porcelain }
    if ($r.Code -ne 0) { Fail "git status failed: $($r.Text)" }
    if ($r.Text.Trim()) {
        $dirty = $r.Text -split "`n" | Where-Object { $_.Trim() }
        $nonGenerated = $dirty | Where-Object { $_ -notmatch '^.{2}\s+"?(docs/|data/)' }
        # Never fight a human or another agent for the tree (same rule as the watchdog).
        if ($nonGenerated) { Fail "Working tree DIRTY beyond generated artifacts; refusing to rebuild:`n$($r.Text)" }
        (Invoke-Native { git checkout -- docs data }) | Out-Null
        (Invoke-Native { git clean -fd docs data }) | Out-Null
        Log ("Auto-cleaned {0} generated leftovers from a prior interrupted run." -f $dirty.Count) 'WARN'
    }
    $r = Invoke-Native { git pull --rebase -X theirs origin main }
    if ($r.Code -ne 0) {
        (Invoke-Native { git rebase --abort }) | Out-Null
        Fail "git pull --rebase failed; refusing to guess. Reconcile by hand:`n$($r.Text)"
    }
    Log "Tree clean; pulled origin/main."

    # ---- env checks ----------------------------------------------------------
    $r = Invoke-Native { python -c "import pandas,numpy,sklearn,requests,openpyxl;print('ENV OK')" }
    if ($r.Code -ne 0) { Fail "Python env check failed (deps missing?):`n$($r.Text)" }
    Push-Location $Scripts
    $rootChk = (Invoke-Native { python -c "import paths;print(paths.ROOT)" }).Text.Trim()
    $cupyChk = (Invoke-Native { python -c "import cupy;cupy.arange(4).sum();print('CUPY OK')" }).Text.Trim()
    Pop-Location
    # The decoy shadow dir C:\Users\carlo\LTCMA\data ate an entire rebuild once.
    if ($rootChk -ne $Repo) { Fail "paths.ROOT resolves to '$rootChk', expected '$Repo'" }
    Log "Python env OK; paths.ROOT = $rootChk"
    $haveCupy = $cupyChk -match 'CUPY OK'
    if ($haveCupy) { Log "cupy OK -- GPU Monte Carlo (06/07/11) will run." }
    else { Log "cupy unavailable; 06/07/11 will be SKIPPED and the MC keeps its current vintage.`n$cupyChk" 'WARN' }

    if ($DryRun) {
        Remove-Item $AlertFile -ErrorAction SilentlyContinue
        Log "=== DRY RUN OK ($([math]::Round(((Get-Date)-$script:Start).TotalSeconds))s) ==="
        exit 0
    }

    Push-Location $Scripts

    # ---- 2. long history (05b ASSERTS Shiller vintage) -----------------------
    # A successful download is not fresh data: the ie_data URL rotted into a CDN
    # asset that served a 20-month-old file at HTTP 200 for over a year.
    Run-Step '05a_download_longhistory.py' -LoadBearing | Out-Null
    $r5b = Run-Step '05b_parse_longhistory.py' -LoadBearing
    if ($r5b.Text -match 'STALE SHILLER FEED') {
        Pop-Location
        Fail "05b reports a STALE SHILLER FEED -- the CAPE input is frozen. Re-check the download URL on shillerdata.com (and do NOT pin the ?ver= query string)."
    }
    if ($r5b.Text -match 'freshness OK') { Log "Shiller vintage assertion passed." }

    # ---- 3. LTCMA core -------------------------------------------------------
    Run-Step '01_fetch_data.py'        -LoadBearing | Out-Null
    Run-Step '02_fetch_valuations.py'  -LoadBearing | Out-Null
    Run-Step '03_build_model.py'       -LoadBearing | Out-Null
    Run-Step '04_portfolios.py'        -LoadBearing | Out-Null

    # ---- 4. materiality gate -------------------------------------------------
    Log "-- materiality gate (rebuilt data/ vs HEAD)"
    $g = Invoke-Native { python (Join-Path $Scripts 'model_delta_gate.py') }
    foreach ($l in ($g.Text -split "`n")) { if ($l.Trim()) { Log "   $l" } }
    if ($g.Code -eq 2 -and -not $Force) {
        Pop-Location
        # Revert so the next daily refresh is not blocked by a dirty tree (F5) and
        # so nothing half-reviewed can leak out via a later run.
        (Invoke-Native { git checkout -- data }) | Out-Null
        Fail "MATERIALITY GATE BREACH -- the rebuilt model moved more than tolerance. data/ reverted, nothing published. Review the deltas above, then re-run with -Force if the move is real."
    }
    if ($g.Code -eq 2 -and $Force) { Log "Gate breached but -Force given; publishing anyway." 'WARN' }
    if ($g.Code -eq 1) { Log "Gate could not evaluate (exit 1); continuing without it." 'WARN' }

    # ---- 5. risk + simulation: ONE UNIT --------------------------------------
    if ($SkipMC) {
        Log "-SkipMC given; 06/07/11 not run." 'WARN'
    } elseif (-not $haveCupy) {
        Log "cupy unavailable; 06/07/11 not run. Risk+MC stay at their committed vintage." 'WARN'
    } else {
        $mcOK = $true
        foreach ($s in @('06_rebuild_risk.py', '07_montecarlo_gpu.py', '11_montecarlo_regime.py')) {
            $r = Run-Step $s
            if ($r.Code -ne 0) { $mcOK = $false; break }
        }
        if (-not $mcOK) {
            # Partial = worse than stale. Roll the whole block back to one vintage.
            foreach ($f in $MCFiles) { (Invoke-Native { git checkout -- $f }) | Out-Null }
            Log "Risk/MC block FAILED partway; all of 06/07/11's outputs reverted to HEAD so the block keeps one coherent vintage. Model core (01-04) still publishes." 'WARN'
        } else {
            Log "Risk + simulation rebuilt (06 -> 07 -> 11)."
        }
    }

    Pop-Location

    if ($BuildOnly) {
        Log "=== BUILD ONLY OK ($([math]::Round(((Get-Date)-$script:Start).TotalSeconds))s) -- not committing ==="
        exit 0
    }

    # ---- 6. commit data/ on its own (F6) -------------------------------------
    # Generated data never rides in the same commit as source: that pairing is what
    # froze the site for 4 days in June 2026 and made the obvious recovery destructive.
    (Invoke-Native { git add data }) | Out-Null
    $staged = (Invoke-Native { git diff --cached --name-only }).Text.Trim()
    if (-not $staged) {
        Log "Model rebuilt with no data change (inputs unmoved since last run)." 'WARN'
    } else {
        $r = Invoke-Native { git commit -m "chore(model): weekly LTCMA rebuild $Today (01-04 + risk/MC)" }
        if ($r.Code -ne 0) { Fail "git commit failed: $($r.Text)" }
        Log ("Committed model data: {0}" -f (Invoke-Native { git rev-parse --short HEAD }).Text.Trim())
    }

    # ---- 7. publish ----------------------------------------------------------
    if ($Publish) {
        # daily_refresh.ps1 starts with `git checkout -- docs data`, so the commit
        # above is MANDATORY -- otherwise it would throw the whole rebuild away.
        # This is the single most expensive mistake available in this procedure.
        Log "-- -Publish given: handing off to daily_refresh.ps1 (rebuild docs, commit, push, live-verify)"
        $dr = Join-Path $Repo 'daily_refresh.ps1'
        $r = Invoke-Native { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $dr }
        foreach ($l in ($r.Text -split "`n" | Select-Object -Last 25)) { if ($l.Trim()) { Log "   $l" } }
        if ($r.Code -ne 0) { Fail "daily_refresh.ps1 failed after the model rebuild; the model data commit is LOCAL and unpushed. See its own log." }
    } else {
        # Push the data commit so it never sits unpushed overnight (an unpushed
        # local commit in front of an advancing origin is the F6 rebase-trap seed).
        # docs/ is deliberately NOT rebuilt here -- see the header note.
        if ($staged) {
            $r = Invoke-Native { git push origin main }
            if ($r.Code -ne 0) { Fail "git push failed:`n$($r.Text)" }
            Log "Pushed model data to origin/main. The next daily refresh will render it to the site."
        }
    }

    Remove-Item $AlertFile -ErrorAction SilentlyContinue
    Log "=== WEEKLY model rebuild DONE ($([math]::Round(((Get-Date)-$script:Start).TotalSeconds))s) ==="
    exit 0
}
catch {
    Fail ("Unhandled: {0}`n{1}" -f $_.Exception.Message, $_.ScriptStackTrace)
}
