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

PUMPFUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hR7FzH3k8zFz3F5zJwJ6z"

tracked_wallets = []
seen_txs = set()
last_update_id = None

# ===== SEND MESSAGE =====
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })

# ===== GET TOKEN NAME =====
def get_token_name(mint):
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
        data = requests.get(url).json()

        pairs = data.get("pairs", [])
        if pairs:
            return pairs[0]["baseToken"]["name"]
    except:
        pass

    return "Unknown Token"

# ===== COMMAND HANDLER =====
def handle_commands():
    global last_update_id

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            data = requests.get(url).json()

            for update in data["result"]:
                update_id = update["update_id"]

                if last_update_id and update_id <= last_update_id:
                    continue

                last_update_id = update_id

                if "message" not in update:
                    continue

                message = update["message"]

                if message["chat"]["id"] != CHAT_ID:
                    continue

                text = message.get("text", "")

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

                    if len(tracked_wallets) >= 10:
                        send_message("⚠️ Max 10 wallets")
                        continue

                    tracked_wallets.append(wallet)
                    send_message(f"✅ Tracking:\n{wallet_str}")

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
                    send_message(f"🗑 Removed:\n{wallet_str}")

                elif text == "/list":
                    if not tracked_wallets:
                        send_message("📭 No wallets")
                    else:
                        msg = "📋 Tracked:\n"
                        for w in tracked_wallets:
                            msg += str(w) + "\n"
                        send_message(msg)

        except:
            pass

        time.sleep(2)

# ===== DETECT FEE CLAIM + TOKEN =====
def parse_fee_claim(tx_data, wallet):
    try:
        meta = tx_data.transaction.meta
        message = tx_data.transaction.transaction.message

        # check pump.fun interaction
        for ix in message.instructions:
            if str(ix.program_id) == PUMPFUN_PROGRAM:

                # SOL change
                pre = meta.pre_balances
                post = meta.post_balances
                keys = message.account_keys

                for i, acc in enumerate(keys):
                    if str(acc) == str(wallet):
                        if post[i] > pre[i]:
                            sol_amount = (post[i] - pre[i]) / 1e9

                            # 🔥 GET TOKEN CA
                            if meta.post_token_balances:
                                mint = meta.post_token_balances[0].mint
                                token_name = get_token_name(mint)
                            else:
                                mint = "Unknown"
                                token_name = "Unknown"

                            return sol_amount, mint, token_name

    except:
        pass

    return None

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

                    try:
                        tx_data = client.get_transaction(sig)
                    except:
                        continue

                    if not tx_data.value:
                        continue

                    result = parse_fee_claim(tx_data.value, wallet)

                    if result:
                        sol, mint, name = result

                        send_message(
                            f"💰 FEE CLAIM\n"
                            f"Wallet: {wallet}\n"
                            f"Token: {name}\n"
                            f"CA: {mint}\n"
                            f"Amount: {sol:.4f} SOL\n"
                            f"https://solscan.io/tx/{sig}"
                        )

        except:
            pass

        time.sleep(5)

# ===== START =====
threading.Thread(target=handle_commands).start()
threading.Thread(target=track_wallets).start()

print("🚀 Advanced Fee Bot Running...")