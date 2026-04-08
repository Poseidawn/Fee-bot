import time
import requests
import threading
from solana.rpc.api import Client
from solders.pubkey import Pubkey

# ===== CONFIG =====
RPC_URL = "https://mainnet.helius-rpc.com/?api-key=afa7a395-7f7f-41aa-a5cb-90b81aae7290"
BOT_TOKEN = "8779218583:AAGNpgOjvgJr9dw99rm4sY0wU3Uexpw5v9g"
CHAT_ID = -1003795346383

client = Client(RPC_URL)

# ===== LOAD / SAVE =====
def load_wallets():
    try:
        with open("wallets.txt", "r") as f:
            return [Pubkey.from_string(line.strip()) for line in f.readlines()]
    except:
        return []

def save_wallets():
    with open("wallets.txt", "w") as f:
        for w in tracked_wallets:
            f.write(str(w) + "\n")

tracked_wallets = load_wallets()
seen_txs = set()
last_update_id = None

# ===== SEND MESSAGE =====
def send_message(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text
            }
        )
    except Exception as e:
        print("Send error:", e)

# ===== COMMAND HANDLER =====
def handle_commands():
    global last_update_id

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1 if last_update_id else ''}"
            data = requests.get(url).json()

            for update in data["result"]:
                last_update_id = update["update_id"]

                if "message" not in update:
                    continue

                msg = update["message"]

                if msg["chat"]["id"] != CHAT_ID:
                    continue

                text = msg.get("text", "")

                # ===== TRACK =====
                if text.startswith("/track"):
                    parts = text.split()

                    if len(parts) < 2:
                        send_message("❌ Usage:\n/track WALLET")
                        continue

                    wallet_str = parts[1]

                    try:
                        wallet = Pubkey.from_string(wallet_str)
                    except:
                        send_message("❌ Invalid wallet")
                        continue

                    if wallet in tracked_wallets:
                        send_message("⚠️ Already tracking")
                        continue

                    tracked_wallets.append(wallet)
                    save_wallets()

                    send_message(f"✅ Tracking:\n{wallet_str}")

                # ===== REMOVE =====
                elif text.startswith("/remove"):
                    parts = text.split()

                    if len(parts) < 2:
                        send_message("❌ Usage:\n/remove WALLET")
                        continue

                    wallet_str = parts[1]

                    try:
                        wallet = Pubkey.from_string(wallet_str)
                    except:
                        send_message("❌ Invalid wallet")
                        continue

                    if wallet not in tracked_wallets:
                        send_message("⚠️ Not tracked")
                        continue

                    tracked_wallets.remove(wallet)
                    save_wallets()

                    send_message(f"🗑 Removed:\n{wallet_str}")

                # ===== LIST =====
                elif text == "/list":
                    if not tracked_wallets:
                        send_message("📭 No wallets")
                    else:
                        msg_text = "📋 Tracked:\n"
                        for w in tracked_wallets:
                            msg_text += str(w) + "\n"
                        send_message(msg_text)

        except Exception as e:
            print("Command error:", e)

        time.sleep(2)

# ===== TRACKING =====
def track_wallets():
    while True:
        try:
            for wallet in tracked_wallets:
                txs = client.get_signatures_for_address(wallet, limit=5)

                if not txs.value:
                    continue

                for tx in txs.value:
                    sig = tx.signature

                    if sig in seen_txs:
                        continue

                    seen_txs.add(sig)

                    tx_data = client.get_transaction(sig)

                    if not tx_data.value:
                        continue

                    meta = tx_data.value.transaction.meta
                    message = tx_data.value.transaction.transaction.message

                    pre_balances = meta.pre_balances
                    post_balances = meta.post_balances
                    account_keys = message.account_keys

                    for i, acc in enumerate(account_keys):
                        if str(acc) == str(wallet):
                            diff = post_balances[i] - pre_balances[i]

                            # ===== DETECT CLAIM (SOL INCREASE) =====
                            if diff > 1 * 1e9:  # >1 SOL threshold
                                amount = diff / 1e9

                                send_message(
                                    f"💰 FEE CLAIM DETECTED\n\n"
                                    f"Wallet:\n{wallet}\n\n"
                                    f"Amount: {amount:.2f} SOL\n\n"
                                    f"https://solscan.io/tx/{sig}"
                                )

        except Exception as e:
            print("Tracking error:", e)

        time.sleep(5)

# ===== START =====
threading.Thread(target=handle_commands).start()
threading.Thread(target=track_wallets).start()
