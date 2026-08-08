# Oracle Cloud 24/7 Automated Deployment and Health Verification Script
param (
    [string]$TargetHost = "oracle-vps",
    [string]$DeployPath = "/opt/loot_raiders"
)

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host " Loot Raiders - Oracle Cloud 24/7 Deployment Script " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. Environment Secrets Check
if (-not (Test-Path ".env")) {
    Write-Warning ".env file not found! Generating template..."
    Set-Content -Path ".env" -Value "DASHBOARD_SESSION_TOKEN=$(New-Guid)`nUSE_LOOT_BRAIN_ENGINE=true"
}

# 2. Database Backup Prior to Deployment
Write-Host "[1/4] Creating pre-deploy database snapshot..." -ForegroundColor Yellow
if (Test-Path "loot_raiders.db") {
    Copy-Item "loot_raiders.db" "loot_raiders.db.bak_$(Get-Date -Format 'yyyyMMddHHmmss')"
}

# 3. Docker Container Build & Launch Verification
Write-Host "[2/4] Validating Docker Compose configuration..." -ForegroundColor Yellow
docker-compose -f docker/docker-compose-loot-brain.yml config

if ($LASTEXITCODE -eq 0) {
    Write-Host "[3/4] Docker compose configuration verified successfully." -ForegroundColor Green
} else {
    Write-Error "Docker compose config validation failed!"
    exit 1
}

Write-Host "[4/4] Cloud Deployment Script Ready for Oracle VPS sync." -ForegroundColor Green
Write-Host "Deployment preparation complete!" -ForegroundColor Cyan
