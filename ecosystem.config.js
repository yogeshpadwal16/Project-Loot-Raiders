module.exports = {
  apps: [
    {
      name: 'loot-raiders',
      script: 'loot_scraper.py',
      cwd: '/var/www/loot-raiders',
      interpreter: '/var/www/loot-raiders/venv/bin/python', // Uses the virtual environment python interpreter
      autorestart: true,
      watch: false,
      max_memory_restart: '1200M',      // Automatically restart if memory exceeds 1.2GB (prevents VPS freeze due to leaks)
      restart_delay: 5000,               // Wait 5 seconds before restart to allow sockets to clear
      cron_restart: '0 4 * * *',         // Auto-restart at 4:00 AM daily (runs startup zombie cleanup to start fresh)
      env: {
        PYTHONUNBUFFERED: '1',
        TELEGRAM_API_ID: '39413198',
        TELEGRAM_API_HASH: 'YOUR_TELEGRAM_API_HASH',
        TELEGRAM_STRING_SESSION: '1BVtsOKIBu04st5g3ZsmDuWjxc8FZHtqu-cVmrgLiUOFVvO8JvmXinbD7r-J32jvyUQYX9dnhVZt3VIwlDbcjpf1dZgVUEAQSrz52FnB8JU2gUBwlqL4mMPCs7SuWKN8ZUBZY1USO768lP-_ztAKEhm29_kGLxXZbR48PGfmqvkaquR7RmCi9bQH7sBi6YA_Mi7LQUAB3bCWG-Z7RIRvFr4J4laDz9fGYLBizdNhFj1Yf7TjigvaGAsEyTrHoo19j8IGu9jmIF9I7hezYy9_4Cd5w626L1xohX31RlNHuwRRAJbZNd6O1MPWyb4g2h1-T3wv1wF0O-b841pv1cYe0333a6yh6sUI='
      }
    },
    {
      name: 'loot-raiders-backup',
      script: 'scripts/backup_db.py',
      cwd: '/var/www/loot-raiders',
      interpreter: '/var/www/loot-raiders/venv/bin/python',
      autorestart: false,
      cron_restart: '0 */12 * * *',      // Run database backup every 12 hours
      env: {
        PYTHONUNBUFFERED: '1'
      }
    }
  ]
};
