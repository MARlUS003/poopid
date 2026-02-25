import discord
import random
import os

async def scrape_rgbar(ctx, source_channel_id, refresh=False):
    """
    Scrapes messages from the source channel.
    If refresh is True, overwrites the file.
    If refresh is False, appends the latest 10 without duplicates.
    """
    channel = ctx.bot.get_channel(source_channel_id)
    if not channel:
        print(f"Error: Could not find channel {source_channel_id}")
        return

    print(f"Fetching messages from {channel.name}...")
    
    file_path = "bar.txt"
    limit = None if refresh else 10
    mode = "w" if refresh else "a+"
    
    try:
        existing_lines = set()
        # We use a unique separator to treat the multi-line entry as one "unit" in the file
        separator = "||ENTRY_SEP||"

        if not refresh and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content_all = f.read()
                existing_lines = set(content_all.split(separator))

        entries_to_write = []
        async for message in channel.history(limit=limit, oldest_first=refresh):
            if not message.content:
                continue
                
            # Support for internal newlines within the bar content
            clean_content = message.content.replace('\n', '\\n')
            
            # Format based on the provided image:
            # [Author]
            # Content
            # -# (Link)
            formatted_entry = (
                f"[{message.author.display_name}]\n"
                f"{clean_content}\n"
                f"-# ({message.jump_url})"
            )
            
            if refresh or formatted_entry not in existing_lines:
                entries_to_write.append(formatted_entry)

        with open(file_path, mode, encoding="utf-8") as f:
            for entry in entries_to_write:
                f.write(entry + separator)

        print(f"Successfully processed {len(entries_to_write)} messages.")

        # Pick random from history
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                all_text = f.read()
                entries = [e for e in all_text.split(separator) if e.strip()]
            
            if entries:
                random_entry = random.choice(entries).strip()
                # Restore any internal newlines that were escaped
                display_entry = random_entry.replace('\\n', '\n')
                await ctx.send(display_entry)
        
    except Exception as e:
        print(f"An error occurred in bar.py: {e}")