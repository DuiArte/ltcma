<#
.SYNOPSIS
  LTCMA daily website refresh -- Windows-native, fired by Task Scheduler.

.DESCRIPTION
  Single-source-of-truth pipeline (migration 2026-06-10): the generators run
  natively on Windows Python inside THIS repo clone; no WSL involvement.
  Replaces the old two-clone flow (WSL build + thin host wrapper), which is
  retired -- see AI_PROCEDURES\WEBSITE_REFRESH_WINDOWS_MIGRATION.md.

  Flow:
    0. Take the cross-task repo lock (weekly_model_rebuild.ps1 takes the same
       one) so the two jobs can never touch this clone at the same time.
    1. Verify clean tree (auto-clean generated docs/data leftovers), pull --rebase.
    2. Data refresh (best-effort): 08 signals, 09 priced-in, 10 regimes,
       20 regime tracker, 19 stock analysis, 28 EMBER paper-track.
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
# Live-verify target. The page LIST is no longer hard-coded: it is enumerated from
# docs/ after the build, so a page added by a future generator is covered on day 1.
# The old six-URL literal silently excluded backtests/report/signals/glossary and the
# eight stock_*.html pages -- 18 of 24 pages were never live-checked at all.
$SiteBase = 'https://duiarte.github.io/ltcma'

# generators print Unicode and write UTF-8; force UTF-8 mode on Windows Python
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# ---- Logging ----------------------------------------------------------------
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force $LogDir | Out-Null }
function Log {
    param([string]$Msg, [string]$Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Msg
    Write-Host $line
    # Tolerant on purpose: with $ErrorActionPreference='Stop' a full disk makes this
    # throw inside Fail(), which re-enters the catch and dies before REFRESH_ALERT.txt
    # is ever written -- no alert in exactly the case that most needs one.
    Add-Content -Path $LogFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
}

# ---- Cross-task repo lock ---------------------------------------------------
# weekly_model_rebuild.ps1 (Sun 22:00) takes this SAME lock. Both scripts operate
# on this clone and both start by running `git checkout -- docs data` +
# `git clean -fd docs data`, so an overlap lets one wipe the other's in-flight
# output -- and the weekly job could then commit a data/ set that is half its own
# rebuild and half HEAD. The nominal schedules do not overlap, but
# StartWhenAvailable fires a missed Sunday rebuild at next logon, which can land
# minutes before this job's 16:31 slot.
#
# A named MUTEX, not a lock file: Task Scheduler kills a run that hits its
# ExecutionTimeLimit and the OS releases an abandoned mutex (caught below, we take
# ownership); a lock file left by that same kill would deadlock every future run.
# Process exit releases it too, so every Fail() path is safe.
$script:RepoMutex = $null
function Enter-RepoLock {
    param([int]$TimeoutMinutes = 25)
    foreach ($n in @('Global\LTCMA_REPO_LOCK', 'Local\LTCMA_REPO_LOCK')) {
        $m = $null
        try { $m = New-Object System.Threading.Mutex($false, $n) } catch { continue }
        $owned = $false
        try { $owned = $m.WaitOne([TimeSpan]::FromMinutes($TimeoutMinutes)) }
        catch [System.Threading.AbandonedMutexException] { $owned = $true }
        if ($owned) { $script:RepoMutex = $m; Log "Repo lock acquired ($n)."; return $true }
        $m.Dispose()
        return $false   # creatable but contended -- a real timeout, not a namespace problem
    }
    Log "Could not create a repo mutex; proceeding WITHOUT cross-task locking." 'WARN'
    return $true
}
function Exit-RepoLock {
    if ($script:RepoMutex) {
        try { $script:RepoMutex.ReleaseMutex() } catch { }
        $script:RepoMutex.Dispose(); $script:RepoMutex = $null
    }
}

function Fail {
    param([string]$Msg)
    Log $Msg 'ERROR'
    Log ("=== refresh FAILED ({0}s) ===" -f [math]::Round(((Get-Date)-$script:Start).TotalSeconds)) 'ERROR'
    # Tripwire. A Fail() used to be indistinguishable from a clean run unless someone
    # opened the log: the 2026-07-27..08-04 outage ran red for seven weekdays and froze
    # the public site for 12 days before anyone noticed. The digests read this file.
    try {
        Set-Content -Path (Join-Path $LogDir 'REFRESH_ALERT.txt') -Encoding utf8 -Value @"
$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') refresh FAILED
$Msg
Log: $LogFile
Nothing was committed or pushed; the public site is still on the last good build.
"@
    } catch { }
    exit 1
}
function Invoke-Native {
    param([scriptblock]$Script)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    # Clear first: every caller runs a NATIVE command, so a command that cannot be
    # launched at all (python off PATH mid-run) leaves LASTEXITCODE at the PREVIOUS
    # step's value -- a prior `git status` 0 would report a generator that never ran
    # as a success. $null propagates and `$null -ne 0` is true, so callers fail loudly.
    $global:LASTEXITCODE = $null
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

    # ---- 0. cross-task repo lock -------------------------------------------
    if (-not (Enter-RepoLock -TimeoutMinutes 25)) {
        Fail "Another LTCMA job holds the repo lock and did not release it within 25 min (weekly_model_rebuild.ps1 running long, or a wedged run). Refusing to build -- a concurrent 'git checkout -- docs data' would destroy its in-flight model rebuild."
    }

    # ---- 1. clean tree + pull ----------------------------------------------
    $r = Invoke-Native { git status --porcelain }
    if ($r.Code -ne 0) { Fail "git status failed: $($r.Text)" }
    if ($r.Text.Trim()) {
        # Classify on the RAW porcelain line: `XY PATH`, XY exactly two status chars.
        # Trimming first strips the status column, so the old alternation only ever
        # covered M/MM/?? -- a deleted or added generated page (' D docs/x', 'A  docs/x',
        # 'UU ...', 'R  a -> b') fell through to "non-generated" and hard-aborted the run.
        $dirty = $r.Text -split "`n" | Where-Object { $_.Trim() }
        $nonGenerated = $dirty | Where-Object { $_ -notmatch '^.{2}\s+"?(docs/|data/)' }
        if ($nonGenerated) { Fail "Working tree DIRTY beyond generated artifacts:`n$($r.Text)" }
        (Invoke-Native { git checkout -- docs data }) | Out-Null
        (Invoke-Native { git clean -fd docs data }) | Out-Null
        Log ("Auto-cleaned {0} generated leftovers from a prior interrupted run." -f $dirty.Count) 'WARN'
    }
    # Conflict-safe pull. Generated docs/ + data/ legitimately diverge between the
    # local build and origin on every push, so a plain `git pull --rebase` can STOP
    # on a generated-file conflict and leave the clone half-rebased -- which wedged
    # the daily task for 4 days (the 2026-06-18..23 rebase-trap). `-X theirs` auto-
    # resolves conflicting hunks (every file is regenerated below, so which side wins
    # a generated hunk is irrelevant) so the rebase always COMPLETES instead of hanging.
    $r = Invoke-Native { git pull --rebase -X theirs origin main }
    if ($r.Code -ne 0) {
        # Still failed: clean up the half-done rebase and recover ONLY if the local-
        # vs-origin divergence is generated artifacts (docs/ + data/). If any local
        # commit touched SOURCE (scripts/, *.ps1, *.md, etc.), refuse to auto-reset --
        # that path is how unpushed feature work (e.g. EMBER) could be destroyed -- and
        # stop loudly for a human.
        (Invoke-Native { git rebase --abort }) | Out-Null
        $localFiles = (Invoke-Native { git diff --name-only origin/main...HEAD }).Text.Trim()
        $srcFiles = $localFiles -split "`n" | ForEach-Object { $_.Trim() } |
                    Where-Object { $_ -and ($_ -notmatch '^(docs/|data/)') }
        if ($srcFiles) {
            Fail ("git pull --rebase failed and local commits touch SOURCE files; refusing to auto-reset (manual reconciliation needed):`n{0}" -f ($srcFiles -join "`n"))
        }
        (Invoke-Native { git reset --hard origin/main }) | Out-Null
        Log "pull --rebase conflicted on generated artifacts only; reset to origin/main (local generated commits rebuilt below)." 'WARN'
    }
    Log "Tree clean; pulled origin/main."

    # ---- DryRun: environment checks only ------------------------------------
    $r = Invoke-Native { python -c "import pandas,numpy,plotly,yfinance,openpyxl,markdown,requests;print('ENV OK')" }
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
    Run-Step '28_ember_ensemble.py'  | Out-Null   # accumulates EMBER paper-track NAV (best-effort)

    # ---- 3. site rebuild ------------------------------------------------------
    Run-Step '17_build_site.py'      -LoadBearing | Out-Null
    Run-Step '23_strategies.py'      -LoadBearing | Out-Null
    Run-Step '27_research_notes.py'  | Out-Null
    Run-Step '25_stock_picks.py'     | Out-Null
    Run-Step '21_stock_signals.py'   | Out-Null
    # LoadBearing: portfolio.html has a HARD as-of gate below, so a best-effort 18 is a
    # lie the script tells itself -- it "continues", then dies 4s later on a downstream
    # symptom that names the wrong cause. Any page with an as-of gate needs its
    # generator load-bearing, so the log names the real failure on day 1.
    Run-Step '18_portfolio.py'       -LoadBearing | Out-Null
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
        # Still resolve $hash: the live-verify below reports it, and an unset
        # variable there would blame an empty commit for a Pages failure.
        $hash = (Invoke-Native { git rev-parse --short HEAD }).Text.Trim()
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

    # ---- 7. live verify -- ENFORCING, with retries for Pages deploy lag -------
    # Every page under docs/ is checked for HTTP 200; the pages that carry an
    # "As of" stamp in the freshly-built file must serve that same date live.
    # The stamp-bearing set is derived from the build, never hard-coded, so it
    # tracks generator changes (index.html gained/lost its stamp twice already).
    #
    # This used to log a WARN and still report DONE, which meant an F7 Pages
    # deploy failure -- push green, site frozen -- was indistinguishable from a
    # healthy run in the log. It now fails the run, which writes REFRESH_ALERT.txt.
    $pageFiles = Get-ChildItem (Join-Path $Docs '*.html') |
                 Where-Object { $_.Name -notlike '_scratch*' } | Sort-Object Name
    $stamped = @{}
    foreach ($f in $pageFiles) {
        $hit = Select-String -Path $f.FullName -Pattern ("As of {0}" -f $Today), ("As of {0}" -f $TodayLong) -SimpleMatch |
               Select-Object -First 1
        if ($hit) { $stamped[$f.Name] = $true }
    }
    Log ("Live-verifying {0} pages ({1} of them carry a today-stamped 'As of')." -f $pageFiles.Count, $stamped.Count)

    $maxRounds = 3
    $bad = @()
    for ($round = 1; $round -le $maxRounds; $round++) {
        Log ("Waiting 60s for GitHub Pages (round {0}/{1})..." -f $round, $maxRounds)
        Start-Sleep -Seconds 60
        $bad = @()
        foreach ($f in $pageFiles) {
            $u = "$SiteBase/$($f.Name)"
            try {
                $resp = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 30
                if ($resp.StatusCode -ne 200) { $bad += ("{0} HTTP {1}" -f $f.Name, $resp.StatusCode); continue }
                if ($stamped.ContainsKey($f.Name)) {
                    $ok = ($resp.Content -match ("As of {0}" -f [regex]::Escape($Today))) -or `
                          ($resp.Content -match ("As of {0}" -f [regex]::Escape($TodayLong)))
                    if (-not $ok -and $MorningRun) {
                        $ok = ($resp.Content -match ("As of {0}" -f [regex]::Escape($Yesterday))) -or `
                              ($resp.Content -match ("As of {0}" -f [regex]::Escape($YesterdayLong)))
                    }
                    if (-not $ok) { $bad += ("{0} serving a stale 'As of'" -f $f.Name) }
                }
            } catch {
                $bad += ("{0} unreachable: {1}" -f $f.Name, $_.Exception.Message)
            }
        }
        if ($bad.Count -eq 0) {
            Log ("LIVE OK: all {0} pages HTTP 200; every stamped page shows today (round {1})." -f $pageFiles.Count, $round)
            break
        }
        Log ("LIVE round {0}: {1} page(s) not current yet -- {2}" -f $round, $bad.Count, (($bad | Select-Object -First 6) -join '; ')) 'WARN'
    }
    if ($bad.Count -gt 0) {
        Fail ("Pushed $hash but GitHub Pages is still not serving it after $maxRounds rounds ({0} page(s)). This is failure mode F7 -- check the 'pages build and deployment' workflow, NOT refresh.yml:`n{1}" -f $bad.Count, (($bad | Select-Object -First 12) -join "`n"))
    }

    Remove-Item (Join-Path $LogDir 'REFRESH_ALERT.txt') -ErrorAction SilentlyContinue
    Log "=== refresh DONE ($([math]::Round(((Get-Date)-$script:Start).TotalSeconds))s) ==="
    Exit-RepoLock
    exit 0
}
catch {
    Fail ("Unhandled: {0}`n{1}" -f $_.Exception.Message, $_.ScriptStackTrace)
}
finally { Exit-RepoLock }
