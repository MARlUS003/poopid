import os
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import time
import json
import yaml
import subprocess
import tempfile
import aiohttp
import bar  # Import the new bar logic
import dotenv

# --- CONFIGURATION ---
dotenv.load_dotenv()
TOKEN = os.getenv("TOKEN")
CHARS = "abcdefghijklmnopqrstuvwxyzæøå "
SCORE_FILE = "scores.json"
FRAMEWORK_FILE = "framework.yml"
MAINCHANNEL = 1069557445061521481

# ADD YOUR USER ID HERE
OWNER_IDS = [1271500729537794229]

# Source Channels
RGBAR_SOURCE = 1285532755194810418
RGQUOTE_SOURCE = 1314537013063712768

#---------- OWNER CHECK HELPER ----------

def is_owner_check(ctx):
    return ctx.author.id in OWNER_IDS

#---------- BOT CLASS WITH SYNCING ----------

class PoopidBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="-", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced slash/context commands for {self.user}")

bot = PoopidBot()


#---------- CONTEXT MENU COMMANDS ----------

@bot.tree.context_menu(name="mock")
async def smock_context(interaction: discord.Interaction, message: discord.Message):
    content = message.content
    if not content:
        await interaction.response.send_message("mock XDD", ephemeral=True)
        return
    mocked = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(content))
    await interaction.response.send_message(f"\"{mocked}\" <:smock:1474063707888947291><:smock:1474063707888947291><:smock:1474063707888947291>")


@bot.tree.context_menu(name="To GIF")
async def to_gif_context(interaction: discord.Interaction, message: discord.Message):
    """Converts an attached video or video in embed to an Animated WebP (higher quality/faster than GIF)."""
    video_url = None

    # 1. Check for direct attachments
    video_attachment = next((a for a in message.attachments if a.content_type and "video" in a.content_type), None)
    if video_attachment:
        video_url = video_attachment.url

    # 2. Check for video in embeds
    if not video_url:
        for embed in message.embeds:
            if embed.video and embed.video.url:
                video_url = embed.video.url
                break

    if not video_url:
        await interaction.response.send_message("use the command on a video, you dumbass", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    start_total = time.time()
    print(f"[To GIF] Starting conversion for {video_url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, "input_vid")
        output_path = os.path.join(tmpdir, "output.webp")

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(video_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        await asyncio.to_thread(lambda: open(input_path, 'wb').write(data))
                        print(f"[To GIF] Downloaded {len(data)} bytes")
                    else:
                        await interaction.followup.send("stupid video")
                        return
        except Exception as e:
            await interaction.followup.send(f"Dumbass video wont download >:(: {e}")
            return

        try:
            current_scale_filter = "iw/2:ih/2"
            quality = 60

            def run_ffmpeg_webp(scale_str, q_val):
                print(f"[To GIF] Running FFmpeg: Scale={scale_str}, Q={q_val}")
                # Removing capture_output so logs go to console
                subprocess.run([
                    "ffmpeg", "-i", input_path,
                    "-vcodec", "libwebp",
                    "-filter_complex", f"fps=30,scale={scale_str}:flags=lanczos",
                    "-lossless", "0",
                    "-compression_level", "0",
                    "-q:v", str(q_val),
                    "-loop", "0",
                    "-an",
                    "-y", output_path
                ], check=True)

            await asyncio.to_thread(run_ffmpeg_webp, current_scale_filter, quality)

            attempts = 0
            pixel_scale = 480
            while os.path.exists(output_path) and os.path.getsize(output_path) > 8 * 1024 * 1024 and attempts < 4:
                print(f"[To GIF] Too big ({os.path.getsize(output_path)} bytes), retrying...")
                quality -= 15
                scale_str = f"{pixel_scale}:-1"
                await asyncio.to_thread(run_ffmpeg_webp, scale_str, max(quality, 10))
                pixel_scale = int(pixel_scale * 0.7)
                attempts += 1

            if not os.path.exists(output_path) or os.path.getsize(output_path) > 8 * 1024 * 1024:
                await interaction.followup.send("shit over 8 mb bruh")
                return

            await interaction.followup.send(file=discord.File(output_path, filename="converted.webp"))
            print(f"[To GIF] Done in {time.time() - start_total:.2f}s")

        except Exception as e:
            print(f"[To GIF] Error: {e}")
            await interaction.followup.send(f"ffmpeg killed itself: {e}")


#---------- REGULAR COMMANDS ----------

@bot.command()
@commands.check(is_owner_check)
async def sync(ctx):
    fmt = await ctx.bot.tree.sync()
    await ctx.send(f"Synced {len(fmt)} commands.")

@bot.command()
@commands.check(is_owner_check)
async def bar_cmd(ctx):
    await bar.scrape_rgbar(ctx, RGBAR_SOURCE, refresh=True)

@bot.command()
async def rgbar(ctx):
    await bar.scrape_rgbar(ctx, RGBAR_SOURCE, refresh=False)

@bot.command(name="g")
async def overlay_gif(ctx, gifname: str = None):
    """Overlays a specified gif (from the local folder) on top of a replied message's image or gif."""
    if not gifname:
        return await ctx.send("You need to specify a gif name! Usage: `-g missile` or `-g carcrash`")

    if not ctx.message.reference:
        return await ctx.send(f"Reply to a message to overlay `{gifname}` on it!")

    # Check if the requested gif exists locally
    overlay_asset = os.path.abspath(f"{gifname}.gif")
    if not os.path.exists(overlay_asset):
        return await ctx.send(f"I don't have a gif named `{gifname}.gif` in my folder!")

    replied_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
    media_url = None
    
    if replied_msg.attachments:
        att = replied_msg.attachments[0]
        if any(att.filename.lower().endswith(e) for e in ('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            media_url = att.url
    
    if not media_url and replied_msg.embeds:
        emb = replied_msg.embeds[0]
        target = emb.image or emb.thumbnail
        if target and target.url:
            media_url = target.url

    if not media_url:
        return await ctx.send("I couldn't find an image or gif in that message!")

    # Determine extension of source media
    ext = ".gif"
    for e in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
        if media_url.lower().split('?')[0].endswith(e):
            ext = e
            break

    await ctx.typing()
    start_total = time.time()
    print(f"[Overlay] Starting process for {media_url} with {gifname}")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.abspath(os.path.join(tmpdir, f"base_media{ext}"))
        output_path = os.path.abspath(os.path.join(tmpdir, "overlay_output.webp"))

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(media_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        with open(input_path, 'wb') as f:
                            f.write(data)
                    else:
                        return await ctx.send(f"Download failed: HTTP {resp.status}")
        except Exception as e:
            return await ctx.send(f"Download error: {e}")

        try:
            def get_media_dims(path):
                cmd = [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", path
                ]
                result = subprocess.check_output(cmd).decode().strip()
                w, h = map(int, result.split('x'))
                return w, h

            orig_w, orig_h = await asyncio.to_thread(get_media_dims, input_path)
            
            current_pixel_scale = 800
            current_quality = 60

            def run_ffmpeg_overlay(scale_val, q_val):
                is_animated = ext.lower() in ('.gif', '.webp')
                target_h = int((scale_val / orig_w) * orig_h)
                
                filter_str = (
                    f"[0:v]fps=30,scale={scale_val}:{target_h}:flags=lanczos[base];"
                    f"[1:v]fps=30,scale={scale_val}:{target_h}:flags=lanczos[ovl];"
                    f"[base][ovl]overlay=0:0:shortest=1"
                )
                
                cmd = ["ffmpeg"]
                if not is_animated: cmd += ["-loop", "1"]
                if ext.lower() == '.webp': cmd += ["-vcodec", "libwebp"]
                
                cmd += ["-i", input_path, "-i", overlay_asset]
                if not is_animated: cmd += ["-t", "5"]
                
                cmd += [
                    "-vcodec", "libwebp",
                    "-filter_complex", filter_str,
                    "-lossless", "0", "-compression_level", "0",
                    "-q:v", str(q_val),
                    "-loop", "0", "-an", "-y", output_path
                ]
                subprocess.run(cmd, check=True)

            await asyncio.to_thread(run_ffmpeg_overlay, current_pixel_scale, current_quality)

            attempts = 0
            while os.path.exists(output_path) and os.path.getsize(output_path) > 8 * 1024 * 1024 and attempts < 4:
                current_quality -= 15
                current_pixel_scale = int(current_pixel_scale * 0.7)
                if current_pixel_scale < 150: break
                await asyncio.to_thread(run_ffmpeg_overlay, current_pixel_scale, max(current_quality, 10))
                attempts += 1

            if not os.path.exists(output_path) or os.path.getsize(output_path) > 8 * 1024 * 1024:
                return await ctx.send("File is too chunky even after shrinking.")

            await ctx.send(file=discord.File(output_path, filename=f"{gifname}_overlay.webp"))
            print(f"[Overlay] Done in {time.time() - start_total:.2f}s")

        except Exception as e:
            print(f"[Overlay] FFmpeg error: {e}")
            await ctx.send("Processing failed.")


#---------- FRAMEWORK LOADER ----------

def load_framework():
    if not os.path.exists(FRAMEWORK_FILE):
        return {"responses": {}, "chance_events": {}}
    try:
        with open(FRAMEWORK_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return {
            "responses": data.get("RESPONSES", {}),
            "chance_events": data.get("CHANCE_EVENTS", {})
        }
    except Exception as e:
        print(f"Error loading YAML framework: {e}")
        return {"responses": {}, "chance_events": {}}


#---------- HELPER FUNCTIONS ----------

user_states = {}
minigame_state = {"target": "", "last_gen": 0}

def load_scores():
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_score(user_id, display_name, event_name=None):
    scores = load_scores()
    uid_str = str(user_id)
    if uid_str not in scores:
        scores[uid_str] = {"score": 0, "name": display_name, "chances": {}}
    scores[uid_str]["name"] = display_name
    if event_name:
        scores[uid_str]["chances"][event_name] = scores[uid_str]["chances"].get(event_name, 0) + 1
    else:
        scores[uid_str]["score"] += 1
    with open(SCORE_FILE, "w") as f:
        json.dump(scores, f, indent=4)
    return scores[uid_str]["score"]

def get_config(content, data_dict):
    if not data_dict: return None
    for key, config in data_dict.items():
        if isinstance(key, list):
            if any(content == str(t).lower().strip() for t in key): return config
        elif content == str(key).lower(): return config
    for key, config in data_dict.items():
        triggers = [str(t).lower().strip() for t in key] if isinstance(key, list) else [str(key).lower()]
        for t in triggers:
            if t.startswith("*") and t.endswith("*") and len(t) > 2:
                if t[1:-1] in content: return config
            elif t == "": return config
    return None

def apply_templates(text, msg_obj, replies_count=0):
    if not text: return ""
    content_raw = msg_obj.content if msg_obj else ""
    mock_case = "".join(c.upper() if i % 2 else c.lower() for i, c in enumerate(content_raw))
    words = content_raw.split()
    templates = [
        ("{user}", msg_obj.author.mention if msg_obj else ""),
        ("{name}", msg_obj.author.display_name if msg_obj else ""),
        ("{target}", minigame_state["target"]),
        ("{content}", content_raw),
        ("{mock}", mock_case),
        ("{count}", str(replies_count))
    ]
    for placeholder, value in templates:
        text = str(text).replace(placeholder, str(value))
    for i in range(text.count("{chop}")):
        word = words[i] if i < len(words) else ""
        text = text.replace("{chop}", word, 1)
    return text

async def send_formatted_message(destination, text, msg_obj, config=None):
    replies_list = config.get("replies", []) if config else []
    replies_count = len(replies_list)
    formatted_text = apply_templates(text, msg_obj, replies_count=replies_count)
    use_reply_feature = False
    mention_author = True
    if config and "reply" in config:
        use_reply_feature = True
        reply_cfg = config["reply"]
        if isinstance(reply_cfg, list):
            use_reply_feature = reply_cfg[0]
            if len(reply_cfg) > 1: mention_author = reply_cfg[1]
        else: mention_author = bool(reply_cfg)
    if use_reply_feature and msg_obj:
        sent_msg = await msg_obj.reply(formatted_text, mention_author=mention_author)
    else:
        sent_msg = await destination.send(formatted_text)
    if config and "edit_to" in config:
        await asyncio.sleep(config.get("delay", 0))
        edit_options = config["edit_to"]
        selected_edit = random.choice(edit_options) if isinstance(edit_options, list) else edit_options
        await sent_msg.edit(content=apply_templates(selected_edit, msg_obj, replies_count=replies_count))
    return sent_msg

def generate_new_target():
    target = "".join(random.choice(CHARS) for _ in range(3))
    minigame_state["target"] = target
    minigame_state["last_gen"] = time.time()
    return target


#---------- EVENTS ----------

@bot.event
async def on_ready():
    generate_new_target()
    print(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    await bot.process_commands(message)
    content_lower = message.content.lower()
    user_id, current_time = message.author.id, time.time()
    fw = load_framework()
    RESPONSES, CHANCE_EVENTS = fw["responses"], fw["chance_events"]

    if content_lower == "___lb":
        scores = load_scores()
        if not scores: return await message.channel.send("noobs")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
        lb = "**--LEADERBOARD--**\n```"
        for i, (uid, d) in enumerate(sorted_scores[:10], 1):
            lb += f"{i}. {d['name']}: {d['score']}\n"
        await message.channel.send(lb + "```")
        return

    if content_lower == "what was?":
        old_target = minigame_state["target"]
        generate_new_target()
        await message.reply(f'"{old_target}", dumbass')
        return

    if current_time - minigame_state["last_gen"] > 43200: generate_new_target()

    target = minigame_state["target"]
    if target and target in content_lower:
        save_score(user_id, message.author.display_name)
        original_msg = message.content
        trigger_index = content_lower.find(target)
        if trigger_index != -1:
            part_to_bold = original_msg[trigger_index:trigger_index+len(target)]
            triggered_sentence = original_msg[:trigger_index] + f"**{part_to_bold}**" + original_msg[trigger_index+len(target):]
        else:
            triggered_sentence = original_msg
        await message.reply(f"yippie, it was \"{target}\"! what triggered it was \"{triggered_sentence}\"")
        generate_new_target()
        return

    if user_id in user_states:
        state = user_states[user_id]
        if current_time - state["time"] < 10:
            parent_cfg = state["config"]
            if sub_cfg := get_config(content_lower, parent_cfg.get("submessages", {})):
                if "edit_to" in sub_cfg:
                    await state["bot_msg"].edit(content=apply_templates(random.choice(sub_cfg["edit_to"]) if isinstance(sub_cfg["edit_to"], list) else sub_cfg["edit_to"], message))
                elif "replies" in sub_cfg:
                    await send_formatted_message(message.channel, random.choice(sub_cfg["replies"]), message, sub_cfg)
                del user_states[user_id]
                return
        else: del user_states[user_id]

    if config := get_config(content_lower, RESPONSES):
        replies = config.get("replies", [])
        if replies:
            msg = await send_formatted_message(message.channel, random.choice(replies), message, config)
            user_states[user_id] = {"config": config, "time": current_time, "bot_msg": msg}
            return

    for name, cfg in CHANCE_EVENTS.items():
        if random.randint(1, int(cfg.get("chance", 1000))) == 1:
            save_score(user_id, message.author.display_name, event_name=name)
            if replies := cfg.get("replies", []):
                msg = await send_formatted_message(message.channel, random.choice(replies), message, cfg)
                user_states[user_id] = {"config": cfg, "time": current_time, "bot_msg": msg}
                break

if __name__ == "__main__":
    bot.run(TOKEN)
