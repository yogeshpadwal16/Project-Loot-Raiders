# ==============================================================================
# 🚀 Project Loot Raiders - Dragonfly & n8n Docker Deployment Automation
# Run this on your local machine to deploy background containers on the VPS.
# ==============================================================================

$IP = "92.4.70.19"
$KEY_PATH = "C:\Users\yoges\Downloads\ssh-key-2026-07-18.key"
$LOCAL_YAML = "C:\Users\yoges\Desktop\Project Loot Raiders\docker\docker-compose-services.yml"

Write-Host "=== 1. Preparing remote workspace directory ===" -ForegroundColor Cyan
$PREPARE_CMD = @'
sudo mkdir -p /var/www/docker-services
sudo chown -R ubuntu:ubuntu /var/www/docker-services
'@
$PREPARE_CMD = $PREPARE_CMD -replace "`r", ""
ssh -o StrictHostKeyChecking=no -i $KEY_PATH "ubuntu@${IP}" $PREPARE_CMD

Write-Host "=== 2. Uploading docker-compose-services.yml to remote host ===" -ForegroundColor Cyan
scp -o StrictHostKeyChecking=no -i $KEY_PATH $LOCAL_YAML "ubuntu@${IP}:/var/www/docker-services/"

Write-Host "=== 3. Starting Dragonfly and n8n Container Services ===" -ForegroundColor Cyan
$START_CMD = @'
cd /var/www/docker-services
sudo docker compose -f /var/www/docker-services/docker-compose-services.yml down 2>/dev/null || true
sudo docker compose -f /var/www/docker-services/docker-compose-services.yml up -d
echo "Services status checking:"
sudo docker compose -f /var/www/docker-services/docker-compose-services.yml ps
'@
$START_CMD = $START_CMD -replace "`r", ""
ssh -o StrictHostKeyChecking=no -i $KEY_PATH "ubuntu@${IP}" $START_CMD

Write-Host "=== 🎉 Dragonfly & n8n Containers Deployed Successfully! ===" -ForegroundColor Green
Write-Host "Dragonfly (Redis) is live on port 6379" -ForegroundColor Green
Write-Host "n8n Automation Console is live on http://${IP}:5678" -ForegroundColor Green
