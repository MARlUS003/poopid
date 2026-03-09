import os
import random

CLIP_LOG = os.path.join("log", "clip.txt")
CLIPS_SOURCE = 1192230255558140004


async def scrape_clips_source(ctx, bot):
    """Scrape video messages from the clips source channel and save links to a file."""
    try:
        print(f"[DEBUG] Starting clip scrape from channel {CLIPS_SOURCE}")
        channel = bot.get_channel(CLIPS_SOURCE)
        if not channel:
            print(f"[DEBUG] Channel not found for ID {CLIPS_SOURCE}")
            await ctx.send(f"Channel not found: {CLIPS_SOURCE}")
            return
        
        print(f"[DEBUG] Found channel: {channel.name} (ID: {channel.id})")
        
        # Clear the log file
        with open(CLIP_LOG, "w", encoding="utf-8") as f:
            f.write("")
        print(f"[DEBUG] Cleared {CLIP_LOG}")
        
        count = 0
        # Scrape messages with video content
        print(f"[DEBUG] Starting to iterate through channel history...")
        async for message in channel.history(limit=None):
            has_video = False
            
            print(f"[DEBUG] Checking message {message.id} from {message.author}")
            
            # Check attachments for video files
            if message.attachments:
                print(f"[DEBUG]   Found {len(message.attachments)} attachment(s)")
                for attachment in message.attachments:
                    print(f"[DEBUG]     Checking attachment: {attachment.filename}")
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.mp4', '.webm', '.mov', '.avi', '.mkv', '.flv']):
                        has_video = True
                        print(f"[DEBUG]     Video attachment detected!")
                        break
            
            # Check embeds for videos
            if not has_video and message.embeds:
                print(f"[DEBUG]   Found {len(message.embeds)} embed(s)")
                for embed in message.embeds:
                    print(f"[DEBUG]     Checking embed type: {embed.type}, has video: {bool(embed.video)}")
                    if embed.video or embed.type == 'video':
                        has_video = True
                        print(f"[DEBUG]     Video embed detected!")
                        break
            
            if has_video:
                # Save the message link
                link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                print(f"[DEBUG]   Saving link: {link}")
                with open(CLIP_LOG, "a", encoding="utf-8") as f:
                    f.write(link + "\n")
                count += 1
        
        print(f"[DEBUG] Scrape complete. Found {count} clips total")
        await ctx.send(f"Scraped {count} clips and saved to {CLIP_LOG}")
    except Exception as e:
        print(f"[DEBUG] Error during scrape: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"Error scraping clips: {e}")


async def forward_random_clip(ctx, bot):
    """Pick a random clip link from log file and forward the message."""
    try:
        print(f"[DEBUG] Starting forward_random_clip")
        print(f"[DEBUG] Clip log file: {CLIP_LOG}")
        
        if not os.path.exists(CLIP_LOG):
            print(f"[DEBUG] Clip log file does not exist")
            await ctx.send("No clips found")
            return
        
        print(f"[DEBUG] Reading clips from {CLIP_LOG}")
        with open(CLIP_LOG, "r", encoding="utf-8") as f:
            links = [line.strip() for line in f if line.strip()]
        
        print(f"[DEBUG] Found {len(links)} links in log file")
        if not links:
            await ctx.send("No clips found")
            return
        
        # Pick random link
        link = random.choice(links)
        print(f"[DEBUG] Selected random link: {link}")
        
        # Extract message ID and channel ID from link
        parts = link.split('/')
        print(f"[DEBUG] Link parts: {parts}")
        message_id = int(parts[-1])
        channel_id = int(parts[-2])
        print(f"[DEBUG] Extracted - Channel ID: {channel_id}, Message ID: {message_id}")
        
        # Get the channel and message
        channel = bot.get_channel(channel_id)
        if not channel:
            print(f"[DEBUG] Channel {channel_id} not found")
            await ctx.send("Channel not found")
            return
        
        print(f"[DEBUG] Found channel: {channel.name}")
        message = await channel.fetch_message(message_id)
        if not message:
            print(f"[DEBUG] Message {message_id} not found in channel {channel_id}")
            await ctx.send("Message not found")
            return
        
        print(f"[DEBUG] Found message, forwarding to {ctx.channel.name}")
        # Forward the message using Discord's built-in forward feature
        await message.forward(destination=ctx.channel)
        print(f"[DEBUG] Message forwarded successfully")
    except Exception as e:
        print(f"[DEBUG] Error during forward: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"Error forwarding clip: {e}")
