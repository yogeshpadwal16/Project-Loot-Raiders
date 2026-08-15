#!/bin/bash
# scripts/setup_ssl_tunnel.sh
# Automated Cloudflare Tunnel & HTTPS setup script for Project Loot Raiders.
# Gives you a free, public HTTPS endpoint (with SSL) for Telegram Mini Apps & Web Storefront.

set -e

echo "================================================================"
echo "🚀 Project Loot Raiders - Cloudflare HTTPS Tunnel Setup"
echo "================================================================"

# 1. Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "📦 Installing official cloudflared binary..."
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
    sudo dpkg -i /tmp/cloudflared.deb || sudo apt-get install -f -y
    rm -f /tmp/cloudflared.deb
    echo "✅ cloudflared installed successfully!"
else
    echo "✅ cloudflared is already installed."
fi

# 2. Check if a PM2 process for cloudflared exists
if pm2 list | grep -q "loot-raiders-tunnel"; then
    echo "🔄 Restarting existing Cloudflare tunnel..."
    pm2 restart loot-raiders-tunnel
else
    echo "🌐 Starting free Cloudflare Quick Tunnel forwarding to http://localhost:5555..."
    pm2 start "cloudflared tunnel --url http://localhost:5555" --name "loot-raiders-tunnel"
    pm2 save
fi

echo "================================================================"
echo "🎉 HTTPS Tunnel is active!"
echo "To view your live public HTTPS URL, run:"
echo "pm2 logs loot-raiders-tunnel --lines 30 --nostream | grep 'trycloudflare.com'"
echo "================================================================"
