$dir = Join-Path $env:USERPROFILE '.claude'
New-Item -ItemType Directory -Force $dir | Out-Null

# 1) status line script
@'
# Status line (Windows / PowerShell): context window fill bar, e.g.  [########------------] 40%
# Claude Code pipes a JSON blob with session info to stdin on every update.
# Non-ASCII characters are built from code points so the file works regardless of its encoding.

$ErrorActionPreference = 'SilentlyContinue'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8

$raw = [Console]::In.ReadToEnd()
$data = $null
if ($raw) { $data = $raw | ConvertFrom-Json }

# Prefer the percentage Claude Code computes; fall back to summing current_usage.
$pct = 0.0
$c = $data.context_window
if ($c -and $null -ne $c.used_percentage) {
    $pct = [double]$c.used_percentage
} elseif ($c -and $c.context_window_size -gt 0 -and $c.current_usage) {
    $u = $c.current_usage
    $tokens = [double]$u.input_tokens + [double]$u.cache_creation_input_tokens + [double]$u.cache_read_input_tokens
    $pct = $tokens * 100 / [double]$c.context_window_size
}
if ($pct -lt 0) { $pct = 0.0 } elseif ($pct -gt 100) { $pct = 100.0 }
$pct = [int][math]::Floor($pct)

$width = 20
$filled = [int][math]::Floor($pct * $width / 100)
$full = [string][char]0x2588
$empty = [string][char]0x2591
$bar = ($full * $filled) + ($empty * ($width - $filled))

# green < 50%, yellow < 80%, red otherwise
$esc = [string][char]27
if ($pct -lt 50) { $color = $esc + '[32m' }
elseif ($pct -lt 80) { $color = $esc + '[33m' }
else { $color = $esc + '[31m' }
$reset = $esc + '[0m'

$out = $color + '[' + $bar + '] ' + $pct + '%' + $reset
$model = $data.model.display_name
if ($model) { $out = $out + ' ' + [char]0x00B7 + ' ' + $model }
[Console]::Out.WriteLine($out)
'@ | Set-Content -Path (Join-Path $dir 'statusline.ps1') -Encoding UTF8

# 2) register it in settings.json (existing settings are kept; backup -> settings.json.bak)
$sf = Join-Path $dir 'settings.json'
$cfg = $null
if (Test-Path $sf) {
    Copy-Item $sf "$sf.bak" -Force
    # Read as UTF-8 explicitly: Windows PowerShell 5.1 Get-Content would decode it as ANSI and mangle non-ASCII text.
    $cfg = [System.IO.File]::ReadAllText($sf, (New-Object System.Text.UTF8Encoding($false))) | ConvertFrom-Json
}
if (-not $cfg) { $cfg = [pscustomobject]@{} }
$script = (Join-Path $dir 'statusline.ps1').Replace('\', '/')
$status = [pscustomobject]@{
    type    = 'command'
    command = 'powershell -NoProfile -ExecutionPolicy Bypass -File "' + $script + '"'
}
$cfg | Add-Member -NotePropertyName statusLine -NotePropertyValue $status -Force
[System.IO.File]::WriteAllText($sf, ($cfg | ConvertTo-Json -Depth 100), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Done: $sf"
