import os
import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import time
import json
import yaml
import bar  # Import the updated bar logic
import media_utils  # Import moved media logic

# --- CONFIGURATION ---
TOKEN = 'MTQ2NzgwOTIzMjEyMzU5Mjg3Ng.G5FwjN.y_oZO4RpaZy6hje9dCvteu2y2Jcm8Wn1ezTunk'
CHARS = "abcdefghijklmnopqrstuvwxyzæøå "
SCORE_FILE = "scores.json"
FRAMEWORK_FILE = "framework.yml"
MAINCHANNEL = 1069557445061521481

# Log Paths
BAR_LOG = os.path.join("log", "bar.txt")
QUOTE_LOG = os.path.join("log", "quotes.txt")

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
        # Syncs global commands (including user-installable ones)
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
    """Converts an attached video or video in embed to an Animated WebP."""
    await media_utils.handle_to_gif(interaction, message)


#---------- REGULAR COMMANDS ----------

@bot.command()
@commands.check(is_owner_check)
async def sync(ctx):
    fmt = await ctx.bot.tree.sync()
    await ctx.send(f"Synced {len(fmt)} commands.")

@bot.command()
@commands.check(is_owner_check)
async def bar_cmd(ctx):
    await bar.scrape_source(ctx, RGBAR_SOURCE, BAR_LOG, "bar")

@bot.command()
async def rgbar(ctx):
    await bar.scrape_source(ctx, RGBAR_SOURCE, BAR_LOG, "bar")

@bot.command()
@commands.check(is_owner_check)
async def quote_cmd(ctx):
    await bar.scrape_source(ctx, RGQUOTE_SOURCE, QUOTE_LOG, "quote")

@bot.hybrid_command(name="rgquote", description="Get a random quote")
async def rgquote(ctx: commands.Context):
    await bar.scrape_source(ctx, RGQUOTE_SOURCE, QUOTE_LOG, "quote")

@bot.hybrid_command(
    name="g", 
    description="Overlay a local gif on a message",
)
@app_commands.describe(gifname="The name of the gif file (without .gif)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def overlay_gif(ctx: commands.Context, gifname: str = None):
    """Overlays a specified gif on top of a replied message's image or gif."""
    await media_utils.handle_overlay_gif(ctx, gifname)


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
        await message.reply(f'"{old_target}", dumb fuck')
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
