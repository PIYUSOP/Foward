import asyncio
import json
import os
import random

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

API_ID = 6435225
API_HASH = "4e984ea35f854762dcde906dce426c2d"

SESSION_STRING = "1BVtsOHYBu2FTJFeLoZQFC-V2rIkL80iFlw8C3YEdEOBwGeyWq_zMxY-XYJvj65vzCmq-H17QfVN8A5DqJTuwvciS5r11EPyaACVBJTF10s1T5raSSEkR9GpYWMmZO6QoKA1-SM9bnB5aCfQbpJDFgAPgyhxk2e_IrSkrPx2PmR7azTgG9bIngRiBTYq7rEm21MNqMWfeUjgC5t8u4YDRvi9NQbZQCeM96qm3sKZd1g71351J2jRd_xXyEhEmVpF92Cqalr6bkH1tqAl7fgKXtgzXqkZkxGPfyB1yPX-WIyLzOCJsAH2ejX1bxF9nPdscHHuD76tq-p6ANSdTZ1guCctdc1cdE0k="

SOURCE_CHANNEL = -1002500303855
DEST_CHANNEL   = -1003724991437

PROGRESS_FILE = "forward.json"

DELAY_MIN = 0.05
DELAY_MAX = 0.08

client = TelegramClient(
    StringSession(SESSION_STRING),
    API_ID,
    API_HASH
)

def load_progress():

    if os.path.exists(PROGRESS_FILE):

        with open(PROGRESS_FILE) as f:
            return json.load(f)

    return {
        "last_id": 0,
        "total": 0
    }

def save_progress(last_id, total):

    with open(PROGRESS_FILE,"w") as f:

        json.dump(
            {
                "last_id": last_id,
                "total": total
            },
            f,
            indent=2
        )

progress = load_progress()

async def fast_delay():

    t = random.uniform(DELAY_MIN, DELAY_MAX)

    await asyncio.sleep(t)

# copy message without forward tag
async def safe_copy(msg):

    while True:

        try:

            await msg.copy_to(DEST_CHANNEL)

            return True

        except FloodWaitError as e:

            print(f"FloodWait {e.seconds} sec")

            await asyncio.sleep(e.seconds + 2)

        except Exception as e:

            print("Error:", e)

            await asyncio.sleep(3)

async def forward_old():

    print("No-quote forwarding started...")

    async for msg in client.iter_messages(
        SOURCE_CHANNEL,
        reverse=True,
        min_id=progress["last_id"]
    ):

        ok = await safe_copy(msg)

        if ok:

            progress["last_id"] = msg.id

            progress["total"] += 1

            save_progress(
                progress["last_id"],
                progress["total"]
            )

            print("Sent:", progress["total"])

            await fast_delay()

@client.on(events.NewMessage(chats=SOURCE_CHANNEL))
async def new_handler(event):

    msg = event.message

    ok = await safe_copy(msg)

    if ok:

        progress["last_id"] = msg.id

        progress["total"] += 1

        save_progress(
            progress["last_id"],
            progress["total"]
        )

        print("New:", msg.id)

        await fast_delay()

async def main():

    print("Starting no-quote forwarder...")

    await client.start()

    print("Logged in")

    await forward_old()

    print("Listening new messages...")

    await client.run_until_disconnected()

asyncio.run(main())
