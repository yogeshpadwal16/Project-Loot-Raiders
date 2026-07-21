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
        TELEGRAM_API_HASH: 'd648fd457db96dffa53ae18d3d1869d8',
        TELEGRAM_STRING_SESSION: '1BVtsOI4Bu3KXmCdLBppBSQyogA7ha8p-Io0pH-Dg_I-fyAB4eGW87HgIb1dZduXL0BubMlQmHReMyGkUWS3rE2WNl47gpdZOZZRAvPQIoHZoePsKUkEvXRmvuhqwClVpi8CYSOpzehbjJZCzBMbxpt0e3C2kGu4lGFfMbGl-qXGZvC_i6_sM9bLc4_KbFRinkEn7Mq4qeJJBB0bBeNn7Vk-InGZ1Jtfdg00kiSUIWjbUcxqM7dnpQVMVmCuQa4oHOArc60gexeK9STJbp6biqtOZN40fbAicFf3brnSDRpcW1cLzOYkUuQrgmYuT9lYzfKtn2KG-qOuXuqXxbi5R3qga7uCJs3s='
      }
    }
  ]
};
