module.exports = {
  apps: [
    {
      name: 'loot-raiders',
      script: 'scripts/start_loot_scraper.sh',
      cwd: '/var/www/loot-raiders',
      autorestart: true,
      watch: false,
      max_memory_restart: '1200M',
      restart_delay: 5000,
      cron_restart: '0 4 * * *',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/var/www/loot-raiders'
      }
    },
    {
      name: 'loot-raiders-mirror',
      script: 'deal_engine/channel_mirror.py',
      cwd: '/var/www/loot-raiders',
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      restart_delay: 5000,
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/var/www/loot-raiders',
        SOURCE_CHANNELS: 'Loot_shoppingdeals123,deals_loot,freekaamaal,desidime_official,loot_deals_box'
      }
    },
    {
      name: 'loot-raiders-backup',
      script: 'scripts/backup_db.py',
      cwd: '/var/www/loot-raiders',
      autorestart: false,
      cron_restart: '0 */12 * * *',
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/var/www/loot-raiders'
      }
    },
    {
      name: 'loot-raiders-briefing',
      script: 'main_briefing.py',
      cwd: '/var/www/loot-raiders',
      autorestart: true,
      watch: false,
      max_memory_restart: '400M',
      restart_delay: 5000,
      env: {
        PYTHONUNBUFFERED: '1',
        PYTHONPATH: '/var/www/loot-raiders'
      }
    }
  ]
};
