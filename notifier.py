import requests

class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send_alert(self, message: str):
        if not self.token or not self.chat_id:
            return
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            response = requests.post(self.base_url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram Alert Error: {e}")
          
