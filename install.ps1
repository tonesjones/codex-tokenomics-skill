[CmdletBinding()]
param(
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' })
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$codexRoot = [IO.Path]::GetFullPath($CodexHome)
$backupRoot = Join-Path $codexRoot ('backups\tokenomics-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))

function Backup-Path([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
        Copy-Item -LiteralPath $Path -Destination $backupRoot -Recurse -Force
    }
}

function Set-TopLevelTomlValue([string]$Text, [string]$Key, [string]$Value) {
    $sectionIndex = $Text.IndexOf("`n[")
    if ($sectionIndex -lt 0) { $sectionIndex = $Text.Length }
    $head = $Text.Substring(0, $sectionIndex)
    $tail = $Text.Substring($sectionIndex)
    $pattern = '(?m)^' + [regex]::Escape($Key) + '\s*=.*$'
    $line = $Key + ' = ' + $Value
    if ([regex]::IsMatch($head, $pattern)) {
        $head = [regex]::Replace($head, $pattern, $line, 1)
    } else {
        $head = $head.TrimEnd() + "`r`n" + $line + "`r`n"
    }
    return $head + $tail
}

New-Item -ItemType Directory -Path $codexRoot -Force | Out-Null
$agentsTarget = Join-Path $codexRoot 'AGENTS.md'
$configTarget = Join-Path $codexRoot 'config.toml'
$skillRoot = Join-Path $codexRoot 'skills'
$tokenomicsTarget = Join-Path $skillRoot 'tokenomics'
$legacyTarget = Join-Path $skillRoot 'cost-aware-delegation'

Backup-Path $agentsTarget
Backup-Path $configTarget
Backup-Path $tokenomicsTarget
Backup-Path $legacyTarget

Copy-Item -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -Destination $agentsTarget -Force
New-Item -ItemType Directory -Path $skillRoot -Force | Out-Null
if (Test-Path -LiteralPath $tokenomicsTarget) { Remove-Item -LiteralPath $tokenomicsTarget -Recurse -Force }
Copy-Item -LiteralPath (Join-Path $repoRoot 'skills\tokenomics') -Destination $tokenomicsTarget -Recurse -Force
if (Test-Path -LiteralPath $legacyTarget) { Remove-Item -LiteralPath $legacyTarget -Recurse -Force }

$configText = if (Test-Path -LiteralPath $configTarget) { Get-Content -Raw -LiteralPath $configTarget } else { '' }
$configText = Set-TopLevelTomlValue $configText 'model' '"gpt-5.6-sol"'
$configText = Set-TopLevelTomlValue $configText 'model_reasoning_effort' '"low"'
$configText = Set-TopLevelTomlValue $configText 'personality' '"pragmatic"'
$configText = Set-TopLevelTomlValue $configText 'service_tier' '"default"'
Set-Content -LiteralPath $configTarget -Value $configText -Encoding utf8

Write-Host "Installed AGENTS.md and the tokenomics skill into $codexRoot"
Write-Host "Applied portable model preferences to $configTarget"
if (Test-Path -LiteralPath $backupRoot) { Write-Host "Previous files were backed up to $backupRoot" }
Write-Host 'Start a new Codex task to load the updated global guidance and skill catalog.'
