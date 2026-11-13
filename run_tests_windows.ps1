# Run from project root using: powershell -ExecutionPolicy Bypass -File .\run_tests_windows.ps1
$ErrorActionPreference = 'Stop'
$dir = Join-Path (Get-Location) 'evidence'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$log = Join-Path $dir "pytest_$stamp.txt"
"Execution date: $(Get-Date -Format o)" | Tee-Object -FilePath $log
"Python version:" | Tee-Object -Append -FilePath $log
python --version 2>&1 | Tee-Object -Append -FilePath $log
"Git commit:" | Tee-Object -Append -FilePath $log
git rev-parse HEAD 2>&1 | Tee-Object -Append -FilePath $log
"Installing dependencies:" | Tee-Object -Append -FilePath $log
python -m pip install -r requirements.txt 2>&1 | Tee-Object -Append -FilePath $log
python -m pip install pytest 2>&1 | Tee-Object -Append -FilePath $log
"Running tests:" | Tee-Object -Append -FilePath $log
$xml = Join-Path $dir "pytest_$stamp.xml"
python -m pytest -v "--junitxml=$xml" 2>&1 | Tee-Object -Append -FilePath $log
$exitCode = $LASTEXITCODE
"pytest exit code: $exitCode" | Tee-Object -Append -FilePath $log
"Evidence log: $log"
exit $exitCode
