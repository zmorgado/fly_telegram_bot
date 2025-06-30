import os
import requests
import logging
from dotenv import load_dotenv
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message: str, parse_mode: str = "HTML"):
    """
    Envía un mensaje de texto al chat de Telegram configurado.
    Permite especificar el parse_mode (por defecto HTML).
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("TELEGRAM_TOKEN y TELEGRAM_CHAT_ID deben estar configurados en variables de entorno.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": parse_mode
    }
    try:
        resp = requests.post(url, data=data, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        logging.error("Error enviando mensaje a Telegram: %s", e)

def send_telegram_pdf(file_path: str, caption: str = ""):
    """
    Envía un archivo PDF al chat de Telegram configurado.
    Permite incluir un caption (mensaje) junto al archivo.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("TELEGRAM_TOKEN y TELEGRAM_CHAT_ID deben estar configurados en variables de entorno.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    files = {'document': open(file_path, 'rb')}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
    try:
        resp = requests.post(url, data=data, files=files, timeout=20)
        resp.raise_for_status()
        logging.info(f"PDF enviado a Telegram con caption: {caption}")
    except requests.RequestException as e:
        logging.error(f"Error enviando PDF a Telegram: {e}")

# def get_chat_id():
#     """
#     Envía un mensaje al bot y obtiene el chat_id del primer usuario que lo contacte.
#     """
#     if not TELEGRAM_TOKEN:
#         print("TELEGRAM_TOKEN debe estar configurado en variables de entorno.")
#         return
#     url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
#     try:
#         resp = requests.get(url, timeout=10)
#         resp.raise_for_status()
#         data = resp.json()
#         for result in data.get("result", []):
#             message = result.get("message")
#             if message and "chat" in message:
#                 chat_id = message["chat"]["id"]
#                 print(f"Tu chat_id es: {chat_id}")
#                 return chat_id
#         print("No se encontró ningún chat_id. Envía un mensaje al bot desde Telegram y vuelve a intentar.")
#     except requests.RequestException as e:
#         print(f"Error obteniendo chat_id: {e}")

# if __name__ == "__main__":
#     get_chat_id()
