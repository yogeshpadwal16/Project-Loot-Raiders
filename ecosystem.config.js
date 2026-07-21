module.exports = {
  apps: [
    {
      name: 'loot-raiders',
      script: 'loot_scraper.py',
      cwd: '/var/www/loot-raiders',
      interpreter: './venv/bin/python', // Uses the virtual environment python interpreter
      autorestart: true,
      watch: false,
      max_memory_restart: '1200M',      // Automatically restart if memory exceeds 1.2GB (prevents VPS freeze due to leaks)
      restart_delay: 5000,               // Wait 5 seconds before restart to allow sockets to clear
      cron_restart: '0 4 * * *',         // Auto-restart at 4:00 AM daily (runs startup zombie cleanup to start fresh)
      env: {
        PYTHONUNBUFFERED: '1'
      }
    }
  ]
};
