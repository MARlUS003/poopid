import os
import discord
import random
import asyncio
import time
import json
import yaml


# --- CONFIGURATION ---
TOKEN = 'MTQ2NzgwOTIzMjEyMzU5Mjg3Ng.G5FwjN.y_oZO4RpaZy6hje9dCvteu2y2Jcm8Wn1ezTunk'
CHARS = "abcdefghijklmnopqrstuvwxyzæøå "
SCORE_FILE = "scores.json"
FRAMEWORK_FILE = "framework.yml"
MAINCHANNEL = 1069557445061521481

# Source Channels
RGBAR_SOURCE = 1285532755194810418
RGQUOTE_SOURCE = 1314537013063712768


# --- PERSISTENT STATE ---
user_states = {}
minigame_state = {"target": "", "last_gen": 0}


#---------- FRAMEWORK LOADER ----------

def load_framework():
    """Reads framework.yml and parses it using PyYAML."""
    if not os.path.exists(FRAMEWORK_FILE):
        print(f"Warning: {FRAMEWORK_FILE} not found.")
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

def load_scores():
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_score(user_id, display_name, event_name=None):
    scores = load_scores()
    uid_str = str(user_id)

    if uid_str not in scores:
        scores[uid_str] = {"score": 0, "name": display_name, "chances": {}}

    scores[uid_str]["name"] = display_name
    if "chances" not in scores[uid_str]:
        scores[uid_str]["chances"] = {}

    if event_name:
        scores[uid_str]["chances"][event_name] = scores[uid_str]["chances"].get(event_name, 0) + 1
    else:
        scores[uid_str]["score"] += 1

    with open(SCORE_FILE, "w") as f:
        json.dump(scores, f, indent=4)
    return scores[uid_str]["score"]


def get_config(content, data_dict):
    """
    Matches content against keys. 
    Strictly treats strings as literals. Multiple triggers must use YAML lists.
    """
    if not data_dict: return None
    
    # Priority 1: Exact Matches
    for key, config in data_dict.items():
        # Case A: Key is a list [trigger1, trigger2]
        if isinstance(key, list):
            if any(content == str(t).lower().strip() for t in key):
                return config
        
        # Case B: Key is a single string (No more comma splitting!)
        else:
            if content == str(key).lower():
                return config
            
    # Priority 2: Wildcard and Catch-all matches
    for key, config in data_dict.items():
        # Get a list of triggers to check (either the list itself or a single-item list)
        triggers = [str(t).lower().strip() for t in key] if isinstance(key, list) else [str(key).lower()]

        for t in triggers:
            if t.startswith("*") and t.endswith("*") and len(t) > 2:
                if t[1:-1] in content: 
                    return config
            elif t == "":
                return config
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
            if len(reply_cfg) > 1:
                mention_author = reply_cfg[1]
        else:
            mention_author = bool(reply_cfg)

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


#---------- BOT ----------

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    generate_new_target()
    print(f'Logged in as {client.user}')


@client.event
async def on_message(message):
    if message.author == client.user: return
    content = message.content.lower()
    user_id, current_time = message.author.id, time.time()

    fw = load_framework()
    RESPONSES, CHANCE_EVENTS = fw["responses"], fw["chance_events"]

    # --- COMMANDS ---
    if content == "check seam":
        await message.channel.send("gnome rash")
        return

    if content == "___lb":
        scores = load_scores()
        if not scores: return await message.channel.send("noobs")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
        lb = "**--LEADERBOARD--**\n```"
        for i, (uid, d) in enumerate(sorted_scores[:10], 1):
            lb += f"{i}. {d['name']}: {d['score']}\n"
        await message.channel.send(lb + "```")
        return

    if content == "clb":
        scores = load_scores()
        if not scores: return await message.channel.send("noobs")
        all_events = set()
        for u_data in scores.values():
            all_events.update(u_data.get("chances", {}).keys())
        if not all_events:
            return await message.channel.send("no chance events recorded yet")
        lb = "**--CHANCE LEADERBOARD--**\n"
        for event in sorted(list(all_events)):
            lb += f"\n> **{event.upper()}**\n```"
            event_users = [(d["name"], d.get("chances", {}).get(event, 0)) for d in scores.values() if d.get("chances", {}).get(event, 0) > 0]
            event_users.sort(key=lambda x: x[1], reverse=True)
            for i, (name, count) in enumerate(event_users[:10], 1):
                lb += f"{i}. {name}: {count}\n"
            lb += "```"
        await message.channel.send(lb)
        return

    if content in ["rgbar", "rgquote"]:
        source_id = RGBAR_SOURCE if content == "rgbar" else RGQUOTE_SOURCE
        source_channel = client.get_channel(source_id)
        if not source_channel: return await message.channel.send("couldn't find source channel")
        try:
            msgs = [m async for m in source_channel.history(limit=100) if m.content]
            if not msgs: return await message.channel.send("no messages found")
            random_msg = random.choice(msgs)
            await message.channel.send(f"{random_msg.content}\n\n[link](<{random_msg.jump_url}>)")
        except Exception as e: await message.channel.send(f"error: {str(e)}")
        return

    if current_time - minigame_state["last_gen"] > 43200: generate_new_target()

    if content == "what was?":
        config = get_config(content, RESPONSES)
        if config:
            replies = config.get("replies", [])
            if replies:
                await send_formatted_message(message.channel, replies[0], message, config)
                generate_new_target()
        return

    if minigame_state["target"] and minigame_state["target"] in content:
        save_score(user_id, message.author.display_name)
        await send_formatted_message(message.channel, "yippie, det var \"{target}\"!", message)
        generate_new_target()
        return

    # --- SUBMESSAGE LOGIC ---
    if user_id in user_states:
        state = user_states[user_id]
        if current_time - state["time"] < 10:
            parent_cfg = state["config"]
            if sub_cfg := get_config(content, parent_cfg.get("submessages", {})):
                if "edit_to" in sub_cfg:
                    edit_options = sub_cfg["edit_to"]
                    selected_edit = random.choice(edit_options) if isinstance(edit_options, list) else edit_options
                    await state["bot_msg"].edit(content=apply_templates(selected_edit, message))
                elif "replies" in sub_cfg:
                    await send_formatted_message(message.channel, random.choice(sub_cfg["replies"]), message, sub_cfg)
                
                del user_states[user_id]
                return
        else: del user_states[user_id]

    # --- MAIN RESPONSES ---
    if config := get_config(content, RESPONSES):
        replies = config.get("replies", [])
        if replies:
            msg = await send_formatted_message(message.channel, random.choice(replies), message, config)
            user_states[user_id] = {"config": config, "time": current_time, "bot_msg": msg}
            return

    # --- CHANCE EVENTS ---
    for name, cfg in CHANCE_EVENTS.items():
        chance_val = cfg.get("chance", 1000)
        if random.randint(1, int(chance_val)) == 1:
            save_score(user_id, message.author.display_name, event_name=name)
            replies = cfg.get("replies", [])
            if replies:
                msg = await send_formatted_message(message.channel, random.choice(replies), message, cfg)
                user_states[user_id] = {"config": cfg, "time": current_time, "bot_msg": msg}
                break


if __name__ == "__main__":
    client.run(TOKEN)
