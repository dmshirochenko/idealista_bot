import yaml
import requests
import os
import logging
import platform

# Basic logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def send_telegram_alert(bot_token, chat_id, message):
    """Sends a message to a specific Telegram chat."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"Successfully sent alert to chat_id {chat_id}")
    except requests.exceptions.RequestException as e:
        # Log to stderr which can be seen in docker logs for the healthcheck
        logging.error(f"Failed to send Telegram alert: {e}")

def main():
    """Main function to load config and send alert."""
    config_path = '/app/config.yaml'
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found at {config_path}")
        return

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file: {e}")
        return

    alerts_config = config.get('telegram_alerts')
    if not alerts_config:
        logging.error("'telegram_alerts' configuration not found in config.yaml")
        return

    bot_token = alerts_config.get('bot_token_alerts')
    chat_id = alerts_config.get('receiver_id_alerts')

    if not bot_token or not chat_id:
        logging.error("Bot token or receiver ID for alerts is missing in config.yaml")
        return

    container_hostname = platform.node() or 'unknown container'
    message = (
        f"<b>🚨 Health Check Failed!</b>\n\n"
        f"The main process <code>flathunt.py</code> is no longer running in container <code>{container_hostname}</code>.\n\n"
        f"The container has been marked as unhealthy and requires manual investigation."
    )
    
    send_telegram_alert(bot_token, chat_id, message)

if __name__ == "__main__":
    main()
