# ==============================================================================
# 🚀 Project Loot Raiders - Shlink URL Shortener Docker Deployment Automation
# Run this on your local machine to install Docker on VPS and launch Shlink.
# ==============================================================================

$IP = "92.4.70.19"
$KEY_PATH = "C:\Users\yoges\Downloads\ssh-key-2026-07-18.key"

Write-Host "=== 1. Checking and Installing Docker Engine on remote VPS ===" -ForegroundColor Cyan
$INSTALL_DOCKER_CMD = @'
# Cleanup any previous malformed APT sources
sudo rm -f /etc/apt/sources.list.d/docker.list
sudo apt-get update -y

if ! command -v docker &> /dev/null; then
    echo "Docker not found. Installing Docker Engine..."
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker ubuntu
    echo "Docker Engine installed successfully!"
else
    echo "Docker is already installed."
fi
'@

$INSTALL_DOCKER_CMD = $INSTALL_DOCKER_CMD -replace "`r", ""
ssh -o StrictHostKeyChecking=no -i $KEY_PATH "ubuntu@${IP}" $INSTALL_DOCKER_CMD

Write-Host "=== 2. Setting up Shlink workspace & docker-compose.yml ===" -ForegroundColor Cyan
$SETUP_SHLINK_CMD = @'
sudo mkdir -p /var/www/shlink
sudo chown -R ubuntu:ubuntu /var/www/shlink

cat << 'EOF' > /var/www/shlink/docker-compose.yml
version: '3.8'

services:
  shlink-db:
    image: postgres:15-alpine
    container_name: shlink-db
    environment:
      POSTGRES_DB: shlink
      POSTGRES_USER: shlink_user
      POSTGRES_PASSWORD: securePassword123
    volumes:
      - shlink_db_data:/var/lib/postgresql/data
    restart: always

  shlink:
    image: shlinkio/shlink:stable
    container_name: shlink-service
    depends_on:
      - shlink-db
    ports:
      - "8080:8080"
    environment:
      - DB_DRIVER=postgres
      - DB_HOST=shlink-db
      - DB_NAME=shlink
      - DB_USER=shlink_user
      - DB_PASSWORD=securePassword123
      - DEFAULT_DOMAIN=go.lootraiders.com
      - IS_HTTPS_ENABLED=false
    restart: always

volumes:
  shlink_db_data:
EOF
'@

$SETUP_SHLINK_CMD = $SETUP_SHLINK_CMD -replace "`r", ""
ssh -o StrictHostKeyChecking=no -i $KEY_PATH "ubuntu@${IP}" $SETUP_SHLINK_CMD

Write-Host "=== 3. Starting Shlink Container Service ===" -ForegroundColor Cyan
$START_SHLINK_CMD = @'
cd /var/www/shlink
sudo docker compose down 2>/dev/null || true
sudo docker compose up -d
echo "Waiting 15 seconds for PostgreSQL and Shlink engine to bootstrap..."
sleep 15
'@

$START_SHLINK_CMD = $START_SHLINK_CMD -replace "`r", ""
ssh -o StrictHostKeyChecking=no -i $KEY_PATH "ubuntu@${IP}" $START_SHLINK_CMD

Write-Host "=== 4. Generating Shlink REST API Key ===" -ForegroundColor Cyan
$GENERATE_KEY_CMD = @'
sudo docker exec shlink-service shlink api-key:create
'@

$GENERATE_KEY_CMD = $GENERATE_KEY_CMD -replace "`r", ""
ssh -o StrictHostKeyChecking=no -i $KEY_PATH "ubuntu@${IP}" $GENERATE_KEY_CMD

Write-Host "=== 🎉 Shlink Container Deployed Successfully! ===" -ForegroundColor Green
Write-Host "Shlink is running locally on http://localhost:8080" -ForegroundColor Green
