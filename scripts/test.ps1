# Build and test the project without adding CLion tools to the system PATH.
[CmdletBinding()]
param(
    [string]$ClionPath,
    [string]$Python,
    [string]$Compiler,
    [string]$CMake
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot

function Find-ExistingTool {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Get-ToolFromPath {
    param([string]$Name)
    $command = Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($command -and $command.Source -notlike '*\Microsoft\WindowsApps\*') {
        return $command.Source
    }
    return $null
}

try {
    $taskClionRoots = @()
    if ($ClionPath) { $taskClionRoots += $ClionPath }
    if ($env:CLION_HOME) { $taskClionRoots += $env:CLION_HOME }
    $taskSearchRoots = @(
        (Join-Path $env:ProgramFiles 'JetBrains'),
        (Join-Path $env:LOCALAPPDATA 'Programs'),
        (Join-Path $env:LOCALAPPDATA 'JetBrains\Toolbox\apps')
    )
    foreach ($searchRoot in $taskSearchRoots) {
        if (Test-Path -LiteralPath $searchRoot -PathType Container) {
            $taskClionRoots += @(Get-ChildItem -LiteralPath $searchRoot -Directory |
                Where-Object { $_.Name -like 'CLion*' } |
                Sort-Object Name -Descending |
                ForEach-Object { $_.FullName })
        }
    }
    $taskClionRoots = @($taskClionRoots | Select-Object -Unique)

    $taskCmakeCandidates = @($CMake, (Get-ToolFromPath 'cmake.exe'))
    $taskNinjaCandidates = @((Get-ToolFromPath 'ninja.exe'))
    $taskCompilerCandidates = @($Compiler, (Get-ToolFromPath 'gcc.exe'),
        (Get-ToolFromPath 'clang.exe'))
    $taskPythonCandidates = @($Python, (Get-ToolFromPath 'python3.exe'),
        (Get-ToolFromPath 'python.exe'))

    foreach ($clionRoot in $taskClionRoots) {
        $taskCmakeCandidates += Join-Path $clionRoot 'bin\cmake\win\x64\bin\cmake.exe'
        $taskNinjaCandidates += Join-Path $clionRoot 'bin\ninja\win\x64\ninja.exe'
        $taskCompilerCandidates += Join-Path $clionRoot 'bin\mingw\bin\gcc.exe'
        $taskPythonCandidates += Join-Path $clionRoot 'bin\lldb\win\x64\bin\python.exe'
    }

    # Also support a normal Python installation and the Windows py launcher.
    $taskPyLauncher = Get-ToolFromPath 'py.exe'
    if ($taskPyLauncher) {
        $taskDiscoveredPython = & $taskPyLauncher -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $taskPythonCandidates += $taskDiscoveredPython }
    }
    $taskPythonInstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $taskPythonInstallRoot -PathType Container) {
        foreach ($installation in Get-ChildItem -LiteralPath $taskPythonInstallRoot -Directory) {
            $taskPythonCandidates += Join-Path $installation.FullName 'python.exe'
        }
    }

    $taskCmake = Find-ExistingTool $taskCmakeCandidates
    $taskNinja = Find-ExistingTool $taskNinjaCandidates
    $taskCompiler = Find-ExistingTool $taskCompilerCandidates
    $taskPython = $null
    foreach ($candidate in $taskPythonCandidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            & $candidate -c 'import sys, argparse, json, pathlib, random, struct, subprocess; sys.exit(0 if sys.version_info >= (3, 8) else 1)' *> $null
            if ($LASTEXITCODE -eq 0) {
                $taskPython = (Resolve-Path -LiteralPath $candidate).Path
                break
            }
        }
    }

    if (-not $taskCmake -or -not $taskNinja -or -not $taskCompiler) {
        throw 'CMake, Ninja or GCC/Clang not found. Install CLion with bundled MinGW, or pass -ClionPath "C:\path\to\CLion".'
    }
    if (-not $taskPython) {
        throw 'Python 3.8+ not found. Install Python or pass -Python "C:\path\to\python.exe".'
    }

    # This changes PATH only inside this script and its child processes.
    $env:PATH = (Split-Path -Parent $taskCompiler) + ';' +
        (Split-Path -Parent $taskNinja) + ';' + $env:PATH
    $env:PYTHONUTF8 = '1'
    $taskBuild = Join-Path $taskRoot 'build\local'
    Write-Host "C compiler: $taskCompiler"
    Write-Host "Python:     $taskPython"
    Write-Host 'Configuring the project...'
    & $taskCmake -S $taskRoot -B $taskBuild -G Ninja '-DCMAKE_BUILD_TYPE=Release' `
        "-DCMAKE_C_COMPILER=$taskCompiler" "-DCMAKE_MAKE_PROGRAM=$taskNinja" `
        "-DPython3_EXECUTABLE=$taskPython" '-DBUILD_TESTING=ON'
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $taskCmake --build $taskBuild --target check --parallel
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Host ''
    Write-Host 'SUCCESS: all tasks passed.' -ForegroundColor Green
    Write-Host "Images: $(Join-Path $taskBuild 'demo')"
    Write-Host "Report: $(Join-Path $taskBuild 'test_report.json')"
    exit 0
} catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}
