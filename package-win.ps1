<#
.SYNOPSIS
    Build and package the Jpylyzer Windows binary distribution for one architecture.

.DESCRIPTION
    Runs PyInstaller against jpylyzer.spec and packages the result as
    dist/<name>_<version>_<suffix>.zip.

    PyInstaller always builds for the architecture of the interpreter that runs it,
    so one invocation covers one architecture. Pass the interpreter that matches
    the requested suffix; the script cross-checks the two before building, because
    a mismatch would otherwise produce a correctly named archive holding binaries
    for the wrong architecture.

    7-Zip is used instead of PowerShell's Compress-Archive, which produces ZIP
    files that do not extract correctly on a Linux system.

.EXAMPLE
    .\package-win.ps1 -Suffix win64
    .\package-win.ps1 -Suffix win32 -Python C:\Python314-32\python.exe
    .\package-win.ps1 -Suffix win64 -Python python -SevenZip 7z
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('win32', 'win64', 'winarm64')]
    [string]$Suffix,

    [string]$Python = 'C:\Python314\python.exe',

    [string]$SevenZip = 'C:\Program Files\7-Zip\7z.exe'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# sysconfig platform name of the interpreter required to build each suffix
$PLATFORM_FOR_SUFFIX = @{
    'win32'    = 'win32'
    'win64'    = 'win-amd64'
    'winarm64' = 'win-arm64'
}

function assertInterpreterTargetsSuffix($python, $suffix) {
    $expected = $PLATFORM_FOR_SUFFIX[$suffix]
    $actual = & $python -c 'import sysconfig; print(sysconfig.get_platform())'
    if ($LASTEXITCODE -ne 0) {
        throw "Could not query interpreter '$python'"
    }
    if ($actual -ne $expected) {
        throw "Interpreter '$python' builds for '$actual', but suffix '$suffix' needs '$expected'"
    }
}

function buildAndPackage($pkgname, $pkgversion, $suffix, $python, $sevenZip) {
    # Define directory paths
    $DIST_DIR = Join-Path -Path $PSScriptRoot -ChildPath "dist"
    $WIN_DIST_DIR = Join-Path -Path $DIST_DIR -ChildPath "windows"
    # Set zip name and path
    $file_name = $pkgname + "_" + $pkgversion + "_" + $suffix + ".zip"
    $zip_name = Join-Path -Path $DIST_DIR -ChildPath $file_name
    $file_spec = $pkgname + ".spec"
    # Remove the windows dist directory if it exists
    if (Test-Path -Path $WIN_DIST_DIR -PathType Container) {
        Remove-Item -Path $WIN_DIST_DIR -Recurse -Force
    }
    # Remove any old instances of this zipped package
    if (Test-Path -Path $zip_name -PathType Leaf) {
        Remove-Item -Path $zip_name -Force
    }
    # Build
    & $python -m PyInstaller --clean -y --distpath $WIN_DIST_DIR $file_spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller exited with code $LASTEXITCODE"
    }

    # Zip up the package and clean up. 7-Zip stores the paths as given on the
    # command line, so the archive keeps the top-level package directory.
    Push-Location $WIN_DIST_DIR
    try {
        & $sevenZip a -tzip $zip_name (Join-Path -Path $pkgname -ChildPath '*')
        if ($LASTEXITCODE -ne 0) {
            throw "7-Zip exited with code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
    Remove-Item -Path $WIN_DIST_DIR -Recurse -Force

    return $zip_name
}

# setup.py and jpylyzer.spec both resolve paths relative to the working directory
Push-Location $PSScriptRoot
try {
    assertInterpreterTargetsSuffix $Python $Suffix

    # Get package name and version
    $pkgname = "$(& $Python .\setup.py --name)"
    $pkgversion = "$(& $Python .\setup.py --version)"

    $zip = buildAndPackage $pkgname $pkgversion $Suffix $Python $SevenZip
    Write-Host "Created $zip"
}
finally {
    Pop-Location
}
