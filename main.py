"""
Main entry point for Telegram IVASMS OTP Bot.
Full-featured version with background monitoring thread.
"""

import os
import logging
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, render_template_string

# ---------------------------
# Attempt to import actual modules
# ---------------------------
try:
    from scraper import IVASMSScraper
    from telegram_bot import TelegramBot
    from utils import setup_logging
    ACTUAL_MODULES = True
except ImportError as e:
    print(f"⚠️ Warning: Could not import actual modules: {e}")
    print("Using dummy classes for testing. Replace with real implementations.")
    ACTUAL_MODULES = False
    
    # Dummy classes for fallback
    class IVASMSScraper:
        def __init__(self, username, password):
            self.username = username
            self.password = password
        def login(self):
            print(f"Dummy login with {self.username}")
            return True
        def check_otp(self):
            # Return dummy OTP for testing
            return [{"otp": "123456", "number": "+1234567890", "service": "Test"}]
    
    class TelegramBot:
        def __init__(self, token, chat_id):
            self.token = token
            self.chat_id = chat_id
        def send_otp(self, otp_data):
            print(f"Dummy send OTP: {otp_data}")
            return True

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ---------------------------
# Environment Variables
# ---------------------------
IVASMS_USERNAME = os.environ.get('IVASMS_USERNAME')
IVASMS_PASSWORD = os.environ.get('IVASMS_PASSWORD')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

missing_vars = []
if not IVASMS_USERNAME: missing_vars.append('IVASMS_USERNAME')
if not IVASMS_PASSWORD: missing_vars.append('IVASMS_PASSWORD')
if not TELEGRAM_BOT_TOKEN: missing_vars.append('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_CHAT_ID: missing_vars.append('TELEGRAM_CHAT_ID')

if missing_vars:
    logger.error(f"Missing environment variables: {', '.join(missing_vars)}. Bot will run in limited mode.")
else:
    logger.info("All environment variables loaded.")

# ---------------------------
# Global State
# ---------------------------
scraper = None
telegram_bot = None
otp_sent_count = 0
last_check_time = None
monitoring_active = False

if not missing_vars:
    try:
        scraper = IVASMSScraper(IVASMS_USERNAME, IVASMS_PASSWORD)
        telegram_bot = TelegramBot(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        logger.info("✅ Scraper and Telegram bot initialized.")
        monitoring_active = True
    except Exception as e:
        logger.exception("Failed to initialize scraper or bot:")
        monitoring_active = False
else:
    monitoring_active = False

# ---------------------------
# Background Monitoring Thread
# ---------------------------
def monitoring_loop():
    """Main monitoring loop – runs every 60 seconds."""
    global otp_sent_count, last_check_time
    logger.info("🚀 Monitoring thread started.")
    while True:
        try:
            if not monitoring_active or not scraper or not telegram_bot:
                logger.warning("Monitoring not active or components missing. Skipping cycle.")
                time.sleep(60)
                continue

            # Ensure logged in (re-login if needed)
            if not scraper.login():
                logger.error("IVASMS login failed. Will retry in 60 seconds.")
                time.sleep(60)
                continue

            # Check for new OTPs
            otps = scraper.check_otp()
            logger.info(f"Checked OTPs, found {len(otps)} new.")
            
            for otp in otps:
                success = telegram_bot.send_otp(otp)
                if success:
                    otp_sent_count += 1
                    logger.info(f"OTP sent: {otp}")
                else:
                    logger.error(f"Failed to send OTP: {otp}")

            last_check_time = datetime.now().isoformat()

        except Exception as e:
            logger.exception("Error in monitoring loop:")
        
        time.sleep(60)  # Wait 1 minute before next check

# Start monitoring thread if conditions are met
if monitoring_active:
    monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitor_thread.start()
    logger.info("✅ Monitoring thread spawned.")
else:
    logger.warning("⚠️ Monitoring thread not started due to missing configuration or initialization failure.")

# ---------------------------
# Flask Web App
# ---------------------------
app = Flask(__name__)

# HTML Dashboard Template (enhanced version)
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🤖 IVASMS OTP Bot</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5; }
        .card { background: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        h1 { color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }
        .stat { display: flex; justify-content: space-between; margin: 10px 0; font-size: 1.1em; }
        .stat-label { color: #666; }
        .stat-value { font-weight: bold; color: #4CAF50; }
        .status-badge { display: inline-block; padding: 5px 10px; border-radius: 20px; font-size: 0.9em; }
        .status-running { background: #d4edda; color: #155724; }
        .status-stopped { background: #f8d7da; color: #721c24; }
        .footer { margin-top: 30px; text-align: center; color: #999; font-size: 0.9em; }
        button { background: #4CAF50; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 1em; }
        button:hover { background: #45a049; }
        .endpoints { margin-top: 20px; }
        .endpoints a { color: #4CAF50; text-decoration: none; }
    </style>
</head>
<body>
    <div class="card">
        <h1>🤖 Telegram IVASMS OTP Bot</h1>
        <p>Automated OTP monitoring and forwarding to Telegram.</p>
        <div>
            <span class="status-badge {{ 'status-running' if monitoring_active else 'status-stopped' }}">
                {{ '🟢 Monitoring Active' if monitoring_active else '🔴 Monitoring Inactive' }}
            </span>
        </div>
    </div>

    <div class="card">
        <h2>📊 Statistics</h2>
        <div class="stat">
            <span class="stat-label">Uptime:</span>
            <span class="stat-value" id="uptime">{{ uptime }}</span>
        </div>
        <div class="stat">
            <span class="stat-label">OTPs Sent:</span>
            <span class="stat-value" id="otp_sent">{{ otp_sent }}</span>
        </div>
        <div class="stat">
            <span class="stat-label">Last Check:</span>
            <span class="stat-value" id="last_check">{{ last_check or 'Never' }}</span>
        </div>
        <div class="stat">
            <span class="stat-label">Cache Size:</span>
            <span class="stat-value" id="cache_size">{{ cache_size }}</span>
        </div>
    </div>

    <div class="card">
        <h2>🛠️ Control & Testing</h2>
        <p>Use these endpoints to test your bot:</p>
        <ul class="endpoints">
            <li><a href="/test-message" target="_blank">📨 Send Test Message</a> – Sends a dummy OTP to your Telegram group.</li>
            <li><a href="/check-otp" target="_blank">🔍 Manual OTP Check</a> – Force a check for new OTPs now.</li>
            <li><a href="/status" target="_blank">📈 JSON Status</a> – Raw status data.</li>
        </ul>
    </div>

    <div class="footer">
        <p>Made with ❤️ for IVASMS users | <a href="https://github.com/ryyzxrv/telegram-ivasms-bot" target="_blank">GitHub</a></p>
    </div>

    <script>
        function updateStats() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('uptime').innerText = data.uptime || '00:00:00';
                    document.getElementById('otp_sent').innerText = data.otp_sent || 0;
                    document.getElementById('last_check').innerText = data.last_check || 'Never';
                    document.getElementById('cache_size').innerText = data.cache_size || 0;
                })
                .catch(err => console.error('Error updating stats:', err));
        }
        // Update every 5 seconds
        setInterval(updateStats, 5000);
        // Initial update
        updateStats();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Render the main dashboard."""
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Get cache size from scraper if available
    cache_size = 0
    if scraper and hasattr(scraper, 'get_cache_size'):
        cache_size = scraper.get_cache_size()
    
    return render_template_string(
        DASHBOARD_HTML,
        uptime=uptime_str,
        otp_sent=otp_sent_count,
        last_check=last_check_time,
        cache_size=cache_size,
        monitoring_active=monitoring_active
    )

@app.route('/status')
def status():
    """Return JSON status for dashboard and API."""
    uptime_seconds = int(time.time() - start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60
    uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    cache_size = 0
    if scraper and hasattr(scraper, 'get_cache_size'):
        cache_size = scraper.get_cache_size()
    
    return jsonify({
        'status': 'running',
        'uptime': uptime_str,
        'otp_sent': otp_sent_count,
        'last_check': last_check_time or 'Never',
        'cache_size': cache_size,
        'monitoring_active': monitoring_active,
        'env_vars_loaded': not missing_vars
    })

@app.route('/test-message')
def test_message():
    """Send a test message to Telegram to verify connectivity."""
    if not telegram_bot:
        return "❌ Telegram bot not initialized. Check environment variables."
    try:
        test_otp = {
            'otp': '123456',
            'number': '+11234567890',
            'service': 'Test Service',
            'time': datetime.now().strftime('%H:%M:%S')
        }
        success = telegram_bot.send_otp(test_otp)
        if success:
            return "✅ Test message sent to Telegram. Check your group."
        else:
            return "❌ Failed to send test message. Check logs."
    except Exception as e:
        return f"❌ Error sending test message: {e}"

@app.route('/check-otp')
def manual_check():
    """Manually trigger an OTP check."""
    global otp_sent_count, last_check_time
    if not scraper or not telegram_bot:
        return "❌ Scraper or bot not initialized."
    try:
        if not scraper.login():
            return "❌ IVASMS login failed."
        otps = scraper.check_otp()
        count = 0
        for otp in otps:
            if telegram_bot.send_otp(otp):
                otp_sent_count += 1
                count += 1
        last_check_time = datetime.now().isoformat()
        return f"✅ Manual check completed. Found {len(otps)} OTPs, sent {count} new."
    except Exception as e:
        return f"❌ Error during manual check: {e}"

@app.route('/health')
def health():
    """Health check endpoint for uptime monitoring."""
    return jsonify({'status': 'healthy'}), 200

# Record start time
start_time = time.time()

# ---------------------------
# Run Flask
# ---------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Note: debug=False is important for production
    app.run(host='0.0.0.0', port=port, debug=False)
