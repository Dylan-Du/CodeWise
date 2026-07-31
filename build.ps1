# build.ps1 — Windows 一键打包成 .exe
# 用法: 在 Windows PowerShell 里运行 .\build.ps1
# 产物: dist\Codex助手.exe

$ErrorActionPreference = "Stop"

$pyCandidates = @("python", "python3", "py")
$PY = $null
foreach ($c in $pyCandidates) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) {
        & $c -c "import tkinter" 2>$null
        if ($LASTEXITCODE -eq 0) { $PY = $c; break }
    }
}
if (-not $PY) {
    Write-Error "找不到带 tkinter 的 Python。请从 python.org 安装 Python 3.11+ 并勾选 'tcl/tk'。"
    exit 1
}

Write-Host "[1/4] 使用 Python: $( & $PY --version )"

Write-Host "[2/4] 安装打包依赖 (pyinstaller / tomlkit / pywebview)"
& $PY -m pip install --upgrade --quiet pyinstaller tomlkit pywebview

Write-Host "[3/4] 清理旧 build/dist"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "[4/4] 运行 PyInstaller"
& $PY -m PyInstaller --clean --noconfirm --windowed --name "Codex助手" `
    --icon "assets\icon-source.png" `
    --add-data "src;src" `
    --add-data "web;web" `
    "src\web_launcher.py"

$exe = "dist\Codex助手\Codex助手.exe"
if (Test-Path $exe) {
    Write-Host ""
    Write-Host "✅ 打包完成: $exe"
    Write-Host "双击运行即可。"
} else {
    Write-Error "打包失败,没看到 $exe"
    exit 1
}
