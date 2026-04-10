import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
import json
import os
from datetime import datetime

# Telethon Config - UPDATED WITH YOUR DETAILS
API_ID = 6435225
API_HASH = "4e984ea35f854762dcde906dce426c2d"
SESSION_STRING = "1BVtsOHYBu12OeJMPmYgDLs9EmjFEeUsVl0bFfvhMf6jBUW3byuAn13rTfHa0QJNZ8WheeAAnvcVefV7yb_va322GPxIgZpkWU6LUpwQfkSdn_A_GUygASZcV2mUeq1UEpvZjp1jieXzQ9Pd9j9tJ554e8fdIwZc6EfTUgXGtjRTiJnvFNTlvRuWiS2s5JsrksEn8Tjjf2uZOzmDK6I7LzPhEjdQxKTbf8_4FWGCryZXGXOVlVhVgLrNCMGfFgbDZr4dwHeDeq7jXeMLaFLK8V64NSnVIkj6yjYT_iphaH4zRz4KEKNMx-WNToONUWuZeyHPM2PD2pCstrCSz70MQ-BbeEt44-k8="

# YOUR CHANNELS
SOURCE_CHANNEL = -1002500303855
DEST_CHANNEL = -1003724991437

PROGRESS_FILE = "telethon_progress.json"

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("Telethon")


class Progress:
    def __init__(self, progress_file=PROGRESS_FILE):
        self.progress_file = progress_file
        self.data = self.load()

    def load(self):
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading: {e}")
        return {"last_id": None, "total": 0, "updated": None}

    def save(self, last_id=None, total=None):
        try:
            if last_id is not None:
                self.data["last_id"] = last_id
            if total is not None:
                self.data["total"] = total
            self.data["updated"] = datetime.now().isoformat()
            with open(self.progress_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving: {e}")

    def get(self):
        return self.data


def is_media(msg):
    """Check if message has video or photo"""
    if not msg.media:
        return False
    
    if msg.photo:
        return True
    
    if msg.video:
        return True
    
    if msg.document and msg.document.mime_type and "video" in msg.document.mime_type:
        return True
    
    return False


async def forward_msg(client, msg_id, retry=0):
    """Forward single message"""
    try:
        await client.forward_messages(
            to_peer=DEST_CHANNEL,
            messages=msg_id,
            from_peer=SOURCE_CHANNEL
        )
        return True
    except FloodWaitError as e:
        logger.warning(f"⚠️  FloodWait {e.seconds}s")
        await asyncio.sleep(min(e.seconds, 10))
        if retry < 1:
            return await forward_msg(client, msg_id, retry + 1)
        return False
    except Exception as e:
        return False


async def get_media(client):
    """Fetch only media messages"""
    msgs = []
    count = 0
    
    logger.warning("📥 Fetching media...")
    
    try:
        async for msg in client.iter_messages(SOURCE_CHANNEL, limit=None):
            if is_media(msg) and msg.id:
                msgs.append(msg)
                count += 1
            
            if count % 500 == 0:
                logger.warning(f"↓ Found {len(msgs)}")
        
        msgs.reverse()
        logger.warning(f"✓ Total media: {len(msgs)}")
        return msgs
    except Exception as e:
        logger.error(f"Error fetching: {e}")
        return []


async def forward_batch(client, msgs, prog):
    """Forward with 15 concurrent"""
    sent = 0
    failed = 0
    batch_size = 15
    
    for i in range(0, len(msgs), batch_size):
        batch = msgs[i:i + batch_size]
        tasks = [forward_msg(client, m.id) for m in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        batch_sent = sum(1 for r in results if r is True)
        batch_failed = len(batch) - batch_sent
        
        sent += batch_sent
        failed += batch_failed
        
        if batch:
            prog.save(batch[-1].id, sent)
        
        if sent % 50 == 0 or i + batch_size >= len(msgs):
            logger.warning(f"⚡ {sent}/{len(msgs)} | Failed: {failed}")
        
        await asyncio.sleep(1.5)
    
    return sent, failed


async def main():
    client = TelegramClient(
        session=StringSession(SESSION_STRING),
        api_id=API_ID,
        api_hash=API_HASH
    )
    
    try:
        await client.connect()
        
        logger.warning("🔥 TELETHON FORWARDER")
        logger.warning(f"Source: {SOURCE_CHANNEL}")
        logger.warning(f"Dest: {DEST_CHANNEL}")
        
        if not await client.is_user_authorized():
            logger.error("❌ Not authorized!")
            return
        
        logger.warning("✓ Authenticated!")
        
        prog = Progress()
        data = prog.get()
        start_from = data.get("last_id")
        
        msgs = await get_media(client)
        
        if not msgs:
            logger.error("❌ No media")
            return
        
        if start_from:
            msgs_forward = [m for m in msgs if m.id > start_from]
            logger.warning(f"Resume from {start_from}")
        else:
            msgs_forward = msgs
        
        if not msgs_forward:
            logger.warning("✓ All done!")
            return
        
        logger.warning(f"Found {len(msgs_forward)} to forward")
        logger.warning("🚀 Starting...")
        
        start = datetime.now()
        total_sent, total_failed = await forward_batch(client, msgs_forward, prog)
        end = datetime.now()
        
        duration = (end - start).total_seconds()
        speed = total_sent / duration if duration > 0 else 0
        success = (total_sent / (total_sent + total_failed) * 100) if (total_sent + total_failed) > 0 else 0
        
        logger.warning(f"""
╔════════════════════════════════════════╗
║        DONE                            ║
╠════════════════════════════════════════╣
║  ✓ Sent: {total_sent:,}
║  ✗ Failed: {total_failed:,}
║  ⏱️  Time: {duration:.1f}s
║  ⚡ Speed: {speed:.1f}/sec
║  📊 Success: {success:.1f}%
╚════════════════════════════════════════╝
        """)
        
        if msgs_forward:
            prog.save(msgs_forward[-1].id, data["total"] + total_sent)
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped")
    except Exception as e:
        logger.error(f"Error: {e}")
