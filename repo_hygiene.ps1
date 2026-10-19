# repo_hygiene.ps1 -- dot-sourced by daily_refresh.ps1 and weekly_model_rebuild.ps1.
# Needs the caller's Log and Invoke-Native functions to be defined first.
#
# WHY (incident 2026-10-09..10-19): an agent session left four uncommitted edits in this
# shared clone (scripts/23_strategies.py + three docs/ files, last touched 2026-10-09 10:03)
# and never came back. The dirty-tree guard refused every run after that: 6 weekday refreshes
# and 2 Sunday model rebuilds failed, and the public site froze at 2026-10-08 for 11 days.
# The guard is right to refuse a tree someone is ACTIVELY editing. A tree nobody has touched
# for $IdleHours is abandoned, and the cost of waiting for its author is a frozen public site.
# So abandoned WIP is set aside, never thrown away: a patch file + a named git stash, plus a
# notice in Downloads so the author finds it.

function Invoke-AbandonedWipStash {
    param(
        [string[]]$Porcelain,                 # git status --porcelain lines (non-generated ones)
        [string]$Job,                         # who is stashing (goes in the stash message)
        [double]$IdleHours = 12
    )
    $newest = $null
    foreach ($line in $Porcelain) {
        $p = $line.Substring(3).Trim().Trim('"')
        if ($p -match ' -> ') { $p = ($p -split ' -> ')[-1].Trim('"') }
        if (Test-Path -LiteralPath $p) {
            $t = (Get-Item -LiteralPath $p -Force).LastWriteTime
            if (-not $newest -or $t -gt $newest) { $newest = $t }
        }
    }
    # Only deletions, or nothing we can date: cannot prove it is idle -> keep refusing.
    if (-not $newest) { Log "Dirty tree has no datable file; not auto-stashing." 'WARN'; return $false }
    $idle = ((Get-Date) - $newest).TotalHours
    if ($idle -lt $IdleHours) {
        Log ("Non-generated edits touched {0:N1} h ago (< {1} h): someone may be working; not auto-stashing." -f $idle, $IdleHours) 'WARN'
        return $false
    }
    $stamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
    $bkDir = 'C:\Users\carlo\Documents\repo_backups\wip'
    try {
        New-Item -ItemType Directory -Force $bkDir | Out-Null
        $patch = Join-Path $bkDir ("LTCMA-website_autostash_{0}.patch" -f $stamp)
        (Invoke-Native { git diff HEAD }).Text | Set-Content -Path $patch -Encoding utf8
        $untracked = (Invoke-Native { git ls-files --others --exclude-standard }).Text
        if ($untracked.Trim()) { Add-Content -Path $patch -Value "`n# UNTRACKED (in the stash, not in this diff):`n$untracked" -Encoding utf8 }
    } catch { Log "Could not write the WIP patch backup: $($_.Exception.Message); not auto-stashing." 'WARN'; return $false }

    $msg = "auto-stash by {0} {1}: abandoned WIP (newest edit {2:yyyy-MM-dd HH:mm}, idle {3:N0} h)" -f $Job, $stamp, $newest, $idle
    $r = Invoke-Native { git stash push --include-untracked -m $msg }
    if ($r.Code -ne 0) { Log "git stash failed: $($r.Text)" 'WARN'; return $false }
    $left = (Invoke-Native { git status --porcelain }).Text -split "`n" |
            Where-Object { $_.Trim() -and $_ -notmatch '^.{2}\s+"?(docs/|data/)' }
    if ($left) { Log "Tree still dirty after stash:`n$($left -join "`n")" 'WARN'; return $false }

    Log ("AUTO-STASHED abandoned WIP ({0:N0} h idle): '{1}'. Patch: {2}. Restore with: git stash list; git stash pop stash@{{N}}" -f $idle, $msg, $patch) 'WARN'
    try {
        Set-Content -Path ("C:\Users\carlo\Downloads\WEBSITE_WIP_AUTOSTASHED_{0}.txt" -f (Get-Date -Format 'yyyy-MM-dd')) -Encoding utf8 -Value @"
$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Job found uncommitted edits in C:\Users\carlo\LTCMA-website
that nobody had touched for $([math]::Round($idle)) h, and set them aside so the site could publish.

Files:
$($Porcelain -join "`n")

Nothing was lost:
  * git stash:  "$msg"   (cd C:\Users\carlo\LTCMA-website; git stash list; git stash pop stash@{N})
  * patch file: $patch

Commit the work (source and generated output in SEPARATE commits) or drop the stash.
"@
    } catch { }
    return $true
}
