module.exports = {
  apps: [
    {
      name: 'loot-raiders',
      script: 'loot_scraper.py',
      cwd: '/var/www/loot-raiders',
      interpreter: '/var/www/loot-raiders/venv/bin/python',
      autorestart: true,
      watch: false,
      max_memory_restart: '1200M',
      restart_delay: 5000,
      cron_restart: '0 4 * * *',
      env: {
        PYTHONUNBUFFERED: '1'
      }
    },
    {
      name: 'loot-raiders-mirror',
      script: 'deal_engine/channel_mirror.py',
      cwd: '/var/www/loot-raiders',
      interpreter: '/var/www/loot-raiders/venv/bin/python',
      autorestart: true,
      watch: false,
      max_memory_restart: '600M',
      restart_delay: 5000,
      env: {
        PYTHONUNBUFFERED: '1',
        SOURCE_CHANNELS: 'Loot_shoppingdeals123,deals_loot,freekaamaal,desidime_official'
      }
    },
    {
      name: 'loot-raiders-backup',
      script: 'scripts/backup_db.py',
      cwd: '/var/www/loot-raiders',
      interpreter: '/var/www/loot-raiders/venv/bin/python',
      autorestart: false,
      cron_restart: '0 */12 * * *',
      env: {
        PYTHONUNBUFFERED: '1'
      }
    },
    {
      name: 'loot-raiders-briefing',
      script: 'main_briefing.py',
      cwd: '/var/www/loot-raiders',
      interpreter: '/var/www/loot-raiders/venv/bin/python',
      autorestart: true,
      watch: false,
      max_memory_restart: '300M',
      restart_delay: 5000,
      env: {
        PYTHONUNBUFFERED: '1'
      }
    }
  ]
};
