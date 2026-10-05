# Builds build\Audio_Processor.exe (single file, no console) and the Desktop
# shortcut. Run from anywhere:  powershell -File scripts\build_exe.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

python scripts\make_icon.py
if ($LASTEXITCODE -ne 0) { throw "icon generation failed" }

# - audioproc.blocks is imported by folder scan, so PyInstaller can't see it
# - scipy is collected whole so user blocks in blocks\ can use any of it;
#   the array_api_compat hidden import is the one the scipy hook misses
#   (same workaround as HackRF SDR TRX)
python -m PyInstaller --noconfirm --onefile --windowed --name Audio_Processor `
    --icon "$root\icon.ico" `
    --add-data "$root\icon.ico;." `
    --add-data "$root\audioproc\ui\arrow.png;audioproc\ui" `
    --add-data "$root\presets;presets" `
    --add-data "$root\blocks;blocks" `
    --collect-submodules audioproc.blocks `
    --collect-data _sounddevice_data --collect-data pyqtgraph `
    --collect-data soundcard --hidden-import soundcard `
    --collect-submodules scipy `
    --hidden-import "scipy._external.array_api_compat.numpy.fft" `
    --distpath build --workpath .pyinstaller_work --specpath .pyinstaller_work `
    run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$exe = Join-Path $root "build\Audio_Processor.exe"
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "Audio Processor.lnk"))
$lnk.TargetPath = $exe
$lnk.WorkingDirectory = Split-Path $exe
$lnk.IconLocation = "$exe,0"
$lnk.Description = "Audio Processor - filter and modify audio"
$lnk.Save()
Write-Host "built $exe and the Desktop shortcut"
