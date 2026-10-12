# Render queue (CPU Cycles). Usage: powershell -File src\render_all.ps1 [-Res 1440,1080] [-Samples 64] [-Jobs "B_full","B_calm"]
param([int[]]$Res = @(1440, 1080), [int]$Samples = 64,
      [string[]]$Jobs = @("B_full", "B_dinner", "B_calm", "B_day", "A_full", "A_calm"))
$root = Split-Path $PSScriptRoot -Parent
$blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
foreach ($j in $Jobs) {
    $cam, $scene = $j.Split("_")
    if (Test-Path "$root\renders\final\$j.exr") { Write-Output "skip $j (exists)"; continue }
    & $blender -b --factory-startup --python "$root\src\blender\build_scene.py" -- --scene $scene --camera $cam `
        --res $Res[0] $Res[1] --samples $Samples --out "$root\renders\final" 2>&1 | Select-String "RENDERED|Traceback|Error:"
}
