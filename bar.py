import discord
import random
import os

async def scrape_source(ctx, source_id, filename, label, refresh=False):
    """
    Fetches messages from the source channel.
    If refresh is True, overwrites the file with the entire channel history.
    If refresh is False, appends the latest 20 without duplicates.
    
    Format in file: [Author]\nContent\n-# (Link)||ENTRY_SEP||
    """
    channel = ctx.bot.get_channel(source_id)
    if not channel:
        return await ctx.send(f"Can't find the {label} source channel.")

    os.makedirs("log", exist_ok=True)
    # Ensure filename points to the correct log directory if not already
    if not filename.startswith("log/"):
        filename = os.path.join("log", filename)
    
    separator = "||ENTRY_SEP||"
    limit = None if refresh else 20
    mode = "w" if refresh else "a"

    # 1. Update the local file with messages
    try:
        async with ctx.typing():
            # Fetch messages
            msgs = [m async for m in channel.history(limit=limit, oldest_first=refresh) if m.content]
            
            existing_entries = set()
            if not refresh and os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    content_all = f.read()
                    existing_entries = set(e.strip() for e in content_all.split(separator) if e.strip())

            entries_to_write = []
            for m in msgs:
                # Escape internal newlines in the message content
                clean_content = m.content.replace('\n', '\\n')
                
                # Construct the entry: [Author]\nContent\n-# (Link)
                formatted_entry = (
                    f"[{m.author.display_name}]\n"
                    f"{clean_content}\n"
                    f"-# ({m.jump_url})"
                )
                
                if refresh or formatted_entry not in existing_entries:
                    entries_to_write.append(formatted_entry)
                    if not refresh:
                        existing_entries.add(formatted_entry)

            # Write entries to file
            if entries_to_write:
                with open(filename, mode, encoding="utf-8") as f:
                    for e in entries_to_write:
                        f.write(e + separator)
                        
        if refresh:
            await ctx.send(f"Successfully refreshed the {label} log with {len(entries_to_write)} messages.")
            
    except Exception as e:
        print(f"Error updating {label} log: {e}")
        await ctx.send(f"Failed to scrape {label} source.")

    # 2. Pick a random entry from the entire log
    if not os.path.exists(filename):
        return await ctx.send(f"The {label} log is empty.")

    try:
        with open(filename, "r", encoding="utf-8") as f:
            all_text = f.read()
            entries = [e for e in all_text.split(separator) if e.strip()]

        if not entries:
            return await ctx.send(f"No {label}s found in log.")

        random_entry = random.choice(entries).strip()
        
        # Restore internal newlines for display
        display_entry = random_entry.replace('\\n', '\n')
        
        # For bars, we send the whole block. 
        # For quotes, we exclude the [Author] header.
        if label == "quote":
            lines = display_entry.split('\n')
            if len(lines) > 1:
                display_entry = '\n'.join(lines[1:]) 
            await ctx.send(display_entry)
        else:
            await ctx.send(display_entry)
            
    except Exception as e:
        await ctx.send(f"Error parsing log entry: {e}")
