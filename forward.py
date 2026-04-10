import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError
import json
import os
from datetime import datetime

# Telethon Config
API_ID = 6435225
API_HASH = "4e984ea35f854762dcde906dce426c2d"
SESSION_STRING = "1BVtsOHYBu12OeJMPmYgDLs9EmjFEeUsVl0bFfvhMf6jBUW3byuAn13rTfHa0QJNZ8WheeAAnvcVefV7yb_va322GPxIgZpkWU6LUpwQfkSdn_A_GUygASZcV2mUeq1UEpvZjp1jieXzQ9Pd9j9tJ554e8fdIwZc6EfTUgXGtjRTiJnvFNTlvRuWiS2s5JsrksEn8Tjjf2uZOzmDK6I7LzPhEjdQxKTbf8_4FWGCryZXGXOVlVhVgLrNCMGfFgbDZr4dwHeDeq7jXeMLaFLK8V64NSnVIkj6yjYT_iphaH4zRz4KEKNMx-WNToONUWuZeyHPM2PD2pCstrCSz70MQ-BbeEt44-k8="

SOURCE_CHANNEL = -1002500303855
DEST_CHANNEL = -1003724991437

PROGRESS_FILE = "telethon_progress.json"

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("Telethon Forwarder")


class TelethonProgress:
    def __init__(self, progress_file=PROGRESS_FILE):
        self.progress_file = progress_file
        self.data = self.load_progress()

    def load_progress(self):
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading progress: {e}")
        return {"last_message_id": None, "total_forwarded": 0, "last_updated": None}

    def save_progress(self, last_msg_id=None, total=None):
        try:
            if last_msg_id is not None:
                self.data["last_message_id"] = last_msg_id
            if total is not None:
                self.data["total_forwarded"] = total
            self.data["last_updated"] = datetime.now().isoformat()
            with open(self.progress_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving progress: {e}")

    def get_progress(self):
        return self.data


def is_media(message):
    """Check if message is video or photo"""
    if not message.media:
        return False, None
    
    # Check for photos
    if message.photo:
        return True, "photo"
    
    # Check for videos
    if message.video:
        return True, "video"
    
    # Check documents that are videos
    if message.document:
        mime = message.document.mime_type or ""
        if "video" in mime:
            return True, "video"
    
    return False, None


async def forward_single_message(client, msg_id):
    """Forward single message"""
    try:
        await client.forward_messages(
            to_peer=DEST_CHANNEL,
            messages=msg_id,
            from_peer=SOURCE_CHANNEL
        )
        return True
    except FloodWaitError as e:
        logger.warning(f"⚠️  FloodWait: {e.seconds}s")
        await asyncio.sleep(min(e.seconds, 5))
        return await forward_single_message(client, msg_id)
    except Exception as e:
        error_str = str(e)[:50]
        if "CHANNEL_PRIVATE" in error_str or "CHAT_FORBIDDEN" in error_str:
            logger.warning(f"✗ Access denied msg {msg_id}")
        return False


async def get_all_media(client):
    """Fetch only video and photo messages"""
    messages = []
    count = 0
    
    logger.info("📥 Fetching media messages...")
    
    try:
        async for message in client.iter_messages(SOURCE_CHANNEL):
            is_media_msg, media_type = is_media(message)
            
            if is_media_msg:
                messages.append(message)
                count += 1
            
            if count % 500 == 0:
                logger.warning(f"↓ Found {len(messages)} media...")
        
        messages.reverse()
        logger.warning(f"✓ Total media: {len(messages)}")
        return messages
    except Exception as e:
        logger.error(f"Error fetching: {e}")
        return []


async def forward_batch(client, messages, progress_manager):
    """Forward with consistent speed - 20 concurrent"""
    total_sent = 0
    failed = 0
    
    batch_size = 20  # Reduced from 50 for stability
    
    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        
        # Create tasks for concurrent execution
        tasks = [forward_single_message(client, msg.id) for msg in batch]
        
        # Execute all at once
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes
        batch_success = sum(1 for r in results if r is True)
        batch_failed = len(batch) - batch_success
        
        total_sent += batch_success
        failed += batch_failed
        
        # Save progress
        if batch:
            last_msg = batch[-1]
            progress_manager.save_progress(last_msg.id, total_sent)
        
        # Log progress
        if total_sent % 100 == 0 or i + batch_size >= len(messages):
            logger.warning(f"⚡ {total_sent}/{len(messages)} sent | Failed: {failed}")
        
        # Consistent delay between batches (1 second for stability)
        await asyncio.sleep(1)
    
    return total_sent, failed


async def main():
    # Create client with StringSession
    client = TelegramClient(
        session=StringSession(SESSION_STRING),
        api_id=API_ID,
        api_hash=API_HASH
    )
    
    try:
        # Connect
        await client.connect()
        
        logger.warning("🔥 TELETHON EXTREME SPEED FORWARDER")
        logger.warning(f"Source: {SOURCE_CHANNEL}")
        logger.warning(f"Dest: {DEST_CHANNEL}")
        logger.warning("Mode: VIDEO + PHOTO ONLY")
        
        # Check if authorized
        if not await client.is_user_authorized():
            logger.error("❌ Not authorized! Session invalid.")
            return
        
        logger.warning("✓ Authenticated!")
        
        # Load progress
        progress_manager = TelethonProgress()
        progress = progress_manager.get_progress()
        start_from = progress.get("last_message_id")
        
        # Fetch media
        messages = await get_all_media(client)
        
        if not messages:
            logger.error("❌ No media to forward")
            return
        
        # Filter messages
        if start_from:
            messages_to_forward = [m for m in messages if m.id > start_from]
            logger.warning(f"Resuming from message {start_from}")
        else:
            messages_to_forward = messages
        
        if not messages_to_forward:
            logger.warning("✓ All media already forwarded!")
            return
        
        logger.warning(f"Found {len(messages_to_forward)} media to forward")
        logger.warning("🚀 Starting EXTREME SPEED forwarding...")
        
        # Forward
        start_time = datetime.now()
        total_sent, total_failed = await forward_batch(
            client, messages_to_forward, progress_manager
        )
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        speed = total_sent / duration if duration > 0 else 0
        success_rate = (total_sent / (total_sent + total_failed) * 100) if (total_sent + total_failed) > 0 else 0
        
        logger.warning(f"""
╔════════════════════════════════════════╗
║        FORWARDING COMPLETE             ║
╠════════════════════════════════════════╣
║  ✓ Forwarded: {total_sent:,}
║  ✗ Failed: {total_failed:,}
║  ⏱️  Time: {duration:.1f} seconds
║  ⚡ Speed: {speed:.1f} msg/sec
║  📊 Success: {success_rate:.1f}%
╚════════════════════════════════════════╝
        """)
        
        # Final save
        if messages_to_forward:
            progress_manager.save_progress(
                messages_to_forward[-1].id,
                progress["total_forwarded"] + total_sent
            )
    
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
