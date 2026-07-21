# ==============================================================================
# 🚀 Project Loot Raiders - Cloud VPS Deployment Automation Script (Tar-based)
# Run this on your local machine to pack, upload, and run the server on the cloud.
# ==============================================================================

$IP = "92.4.70.19"
$KEY_PATH = "C:\Users\yoges\Downloads\ssh-key-2026-07-18.key"
$TAR_PATH = "C:\Users\yoges\Desktop\loot_raiders.tar.gz"

Write-Host "=== 1. Creating clean deployment archive using tar.exe ===" -ForegroundColor Cyan
if (Test-Path $TAR_PATH) { Remove-Item $TAR_PATH -Force }

# Change to project root directory to ensure relative paths in tar are correct
$OriginalLocation = Get-Location
Set-Location "C:\Users\yoges\Desktop\Project Loot Raiders"

# Create a tar.gz archive including essential directories and files (added 'web' folder)
tar.exe -czf $TAR_PATH core dashboard database deal_engine knowledge_base plugins scripts utils config web loot_scraper.py selectors.json settings.json requirements.txt .env ecosystem.config.js

# Restore directory location
Set-Location $OriginalLocation

Write-Host "=== 2. Copying archive to remote VPS ===" -ForegroundColor Cyan
scp -o StrictHostKeyChecking=no -i $KEY_PATH $TAR_PATH "ubuntu@${IP}:/home/ubuntu/"

Write-Host "=== 3. Executing deployment commands on remote VPS ===" -ForegroundColor Cyan
$SSH_CMD = @"
sudo mkdir -p /var/www/loot-raiders
sudo tar -xzf /home/ubuntu/loot_raiders.tar.gz -C /var/www/loot-raiders
sudo chown -R ubuntu:ubuntu /var/www/loot-raiders
rm -f /home/ubuntu/loot_raiders.tar.gz

cd /var/www/loot-raiders

# Setup Python Virtual Environment and Install dependencies
python3 -m venv venv || python3 -m venv --without-pip venv
./venv/bin/python -m ensurepip --upgrade 2>/dev/null || true
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium

# Daemonize process with PM2 using ecosystem configuration
pm2 delete loot-raiders 2>/dev/null || true
pm2 start /var/www/loot-raiders/ecosystem.config.js
pm2 save
"@

# Fix Windows CRLF -> Unix LF before sending to SSH
$SSH_CMD = $SSH_CMD -replace "`r", ""

ssh -o StrictHostKeyChecking=no -i $KEY_PATH "ubuntu@${IP}" $SSH_CMD

Write-Host "=== 🎉 Cloud deployment completed successfully! ===" -ForegroundColor Green
Write-Host "Dashboard is live at http://${IP}:5555/" -ForegroundColor Green

