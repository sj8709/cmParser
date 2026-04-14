# PyInstaller 빌드 스크립트 — chaekmu-parser GUI
# 실행: pwsh scripts/build_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot/.."

$version = (Select-String -Path "src/chaekmu_parser_gui/__init__.py" -Pattern '__version__ = "(.+)"').Matches.Groups[1].Value

Write-Host "=== chaekmu-parser GUI build v$version ===" -ForegroundColor Cyan

# venv 활성화
if (-Not (Test-Path ".venv/Scripts/Activate.ps1")) {
    Write-Error "venv 없음. python -m venv .venv 후 pip install -e `".[gui,build]`" 먼저."
}
. .\.venv\Scripts\Activate.ps1

# 이전 산출물 정리
Remove-Item -Recurse -Force dist/chaekmu-parser, build/chaekmu-parser -ErrorAction SilentlyContinue

# PyInstaller 실행
Write-Host "-> pyinstaller" -ForegroundColor Yellow
pyinstaller build/gui.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

# 배포용 안내 문서 복사
$readme = "docs/읽어보세요.txt"
if (Test-Path $readme) {
    Copy-Item $readme "dist/chaekmu-parser/"
}

# zip 패키징
$zipName = "dist/chaekmu-parser-v$version-win64.zip"
Remove-Item $zipName -ErrorAction SilentlyContinue
Compress-Archive -Path "dist/chaekmu-parser/*" -DestinationPath $zipName -Force

# 번들 크기 리포트
$sizeMB = [math]::Round((Get-Item $zipName).Length / 1MB, 1)
$folderSizeMB = [math]::Round(((Get-ChildItem dist/chaekmu-parser -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB), 1)

Write-Host ""
Write-Host "=== 완료 ===" -ForegroundColor Green
Write-Host "  폴더 크기 : $folderSizeMB MB  (dist/chaekmu-parser/)"
Write-Host "  zip 크기  : $sizeMB MB  ($zipName)"
