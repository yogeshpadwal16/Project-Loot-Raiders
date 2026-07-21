#!/bin/bash
# ==============================================================================
# 🚀 Project Loot Raiders - Oracle Cloud VPS Setup Script
# Run this script on your freshly created Ubuntu VPS instance.
# ==============================================================================

# Exit on error
set -e

echo "=== 1. Updating System Packages ==="
sudo apt-get update && sudo apt-get upgrade -y

echo "=== 2. Installing Python, Git, and build essentials ==="
sudo apt-get install -y python3-pip python3-venv git curl build-essential

echo "=== 3. Installing Node.js & PM2 (Process Manager) ==="
# Node is required for PM2 to daemonize the Python server
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs
sudo npm install -g pm2

echo "=== 4. Setting up Project Directory ==="
# Adjust repository URL as needed
sudo mkdir -p /var/www/loot-raiders
sudo chown -R $USER:$USER /var/www/loot-raiders

echo "=== 5. Clone repository and install Python environment ==="
# The user will clone their git repository here. 
# We'll print instructions at the end.

echo "=== 6. Installing Playwright & System Browsers ==="
# Playwright needs chromium and its system dependencies (GTK, fonts, etc.) to run headless
sudo npx playwright install-deps chromium

echo "=== 7. Configuring Linux Firewall (iptables/ufw) ==="
# Oracle Cloud VMs default to strict iptables. We need to explicitly allow port 5555
if command -v ufw >/dev/null; then
    sudo ufw allow 5555/tcp || true
fi

# Open port 5555 in iptables (Oracle standard)
sudo iptables -I INPUT 6 -p tcp --dport 5555 -j ACCEPT || true
sudo netfilter-persistent save || true

echo ""
echo "======================================================================"
echo "🎉 VPS Core Environment Setup Completed Successfully!"
echo "======================================================================"
echo "Next Steps to deploy code:"
echo "1. Run: cd /var/www/loot-raiders"
echo "2. Clone your repo: git clone <YOUR_REPO_URL> ."
echo "3. Initialize virtual env:"
echo "   python3 -m venv venv"
echo "   source venv/bin/activate"
echo "   pip install -r requirements.txt"
echo "   playwright install chromium"
echo "4. Create your .env file with Telegram tokens:"
echo "   nano .env"
echo "5. Start the scraper 24/7 with PM2 using the ecosystem configuration:"
echo "   pm2 start ecosystem.config.js"
echo "   pm2 save"
echo "   pm2 startup"
echo "======================================================================"
