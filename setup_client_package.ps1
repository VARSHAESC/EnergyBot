# Robust Packaging Script
$Source = Get-Location
$ZipFile = Join-Path $Source.Path "Client_Handoff.zip"
$EnvFile = Join-Path $Source.Path ".env"
$TempBak = Join-Path $Source.Path ".env.bak"
$Template = Join-Path $Source.Path ".env.template"

# 1. Clear old zip
if (Test-Path $ZipFile) { Remove-Item $ZipFile -Force }

# 2. Swap real .env for blank one
$HasRealEnv = Test-Path $EnvFile
if ($HasRealEnv) {
    Rename-Item $EnvFile -NewName ".env.bak"
}
if (Test-Path $Template) {
    Copy-Item $Template $EnvFile
}

# 3. Zip files
$Excludes = @("venv", ".git", "__pycache__", "chroma_db", "cache", "setup_client_package.ps1", "Client_Handoff.zip", ".env.bak")
$Files = Get-ChildItem -Path $Source.Path -Recurse | Where-Object {
    $Name = $_.FullName
    $Skip = $false
    foreach ($Ex in $Excludes) {
        if ($Name -like "*\$Ex*" -or $Name -eq (Join-Path $Source.Path $Ex)) {
            $Skip = $true
            break
        }
    }
    -not $Skip
}

Compress-Archive -Path ($Files.FullName) -DestinationPath $ZipFile -Force

# 4. Restore original state
if (Test-Path $EnvFile) { Remove-Item $EnvFile -Force }
if ($HasRealEnv) {
    Rename-Item $TempBak -NewName ".env"
}

Write-Host "Done: Client_Handoff.zip created."
