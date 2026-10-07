$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$versionSource = Get-Content (Join-Path $projectRoot "src\nemo\version.py") -Raw
if ($versionSource -notmatch 'APP_VERSION\s*=\s*"([^\"]+)"') {
    throw "Could not read the application version from src\nemo\version.py."
}
$appVersion = $Matches[1]

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    py -3 -m venv .venv
    $python = Join-Path $projectRoot ".venv\Scripts\python.exe"
}

& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install NEMO build dependencies." }

$env:PYTHONNOUSERSITE = "1"
$env:PYTHONUSERBASE = Join-Path $projectRoot ".venv\userbase"
& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name NEMO `
    --distpath .nemo-release `
    --workpath .nemo-build\pyinstaller `
    --specpath .nemo-build\spec `
    --paths (Join-Path $projectRoot "src") `
    --add-data "$(Join-Path $projectRoot 'config\settings.yaml');config" `
    (Join-Path $projectRoot "src\nemo\gui.py")
if ($LASTEXITCODE -ne 0) { throw "NEMO desktop build failed." }

$appDirectory = Join-Path $projectRoot ".nemo-release\NEMO"
Copy-Item (Join-Path $projectRoot "README.md") (Join-Path $appDirectory "README.md") -Force
$portableArchive = Join-Path $projectRoot ".nemo-release\NEMO-Windows-Portable.zip"
Compress-Archive -Path (Join-Path $appDirectory "*") -DestinationPath $portableArchive -Force

$compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($null -eq $compiler) {
    Write-Host "Portable app built in .nemo-release\NEMO and .nemo-release\NEMO-Windows-Portable.zip. Install Inno Setup to create the optional setup program."
    exit 0
}

& $compiler.Source "/DNEMOVersion=$appVersion" "/O$(Join-Path $projectRoot '.nemo-release\installer')" installer\NEMO.iss
if ($LASTEXITCODE -ne 0) { throw "NEMO installer build failed." }
Write-Host "NEMO installer created in .nemo-release\installer."
