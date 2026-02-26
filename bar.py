import discord
import random
import os

async def scrape_source(ctx, source_id, filename, label):
    """
    Fetches latest 20 messages, appends new ones to the log file (no duplicates),
    then picks a random entry from the file to display.
    
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

    # 1. Update the local file with new messages
    try:
        async with ctx.typing():
            # Fetch latest 20
            msgs = [m async for m in channel.history(limit=20) if m.content]
            
            # Load existing entries to check for duplicates
            existing_entries = set()
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    content_all = f.read()
                    existing_entries = set(e.strip() for e in content_all.split(separator) if e.strip())

            new_entries = []
            for m in msgs:
                # Escape internal newlines in the message content
                clean_content = m.content.replace('\n', '\\n')
                
                # Construct the entry based on preferred formatting
                # [Author]
                # Content
                # -# (Link)
                formatted_entry = (
                    f"[{m.author.display_name}]\n"
                    f"{clean_content}\n"
                    f"-# ({m.jump_url})"
                )
                
                if formatted_entry not in existing_entries:
                    new_entries.append(formatted_entry)
                    existing_entries.add(formatted_entry)

            # Append new unique entries
            if new_entries:
                with open(filename, "a", encoding="utf-8") as f:
                    for e in new_entries:
                        f.write(e + separator)
    except Exception as e:
        print(f"Error updating {label} log: {e}")

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
            # Split the entry into lines and skip the first line ([Author])
            lines = display_entry.split('\n')
            if len(lines) > 1:
                display_entry = '\n'.join(lines[1:]) 
            await ctx.send(display_entry)
        else:
            await ctx.send(display_entry)
            
    except Exception as e:
        await ctx.send(f"Error parsing log entry: {e}")
