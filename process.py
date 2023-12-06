import sys
import json
import sentencepiece as spm
from datetime import datetime
import random
from wonderwords import RandomWord

rw = RandomWord()

MAX_TOKENS = 4096

sp = spm.SentencePieceProcessor(model_file="./llama-tokenizer.bin")

obj = []
for line in sys.stdin:
    obj.append(json.loads(line))

obj.sort(key=lambda x: x["timestamp"])

buf = []
sys_prompt = "Welcome to Discord, it is {time}, following commands are available:\n/login <username>\n/switch-guild <guild>\n/switch-channel <channel>\n/switch-dm <user>\n/switch-group <group>\n/list-guilds\n/list-channels\n/list-dms\n/list-groups\n/list-friends\nAny other commands will not work, Have fun!"
login_time = 0
last_time = 0
first_time = 0
user = ""
reauser = ""
cur_guild = ""
cur_channel = ""
new_guild = ""
new_channel = ""
new_guild_d = {}
new_channel_d = {}
id_count = 0
ids = {}

def rand_user():
    x = rw.random_words(random.randrange(1, 5), include_parts_of_speech=["verbs", "adjectives", "nouns"], word_max_length=12)
    return ("." if random.random() <= 0.5 else "_").join(x)

def id_convert(id):
    global id_count
    ids[id] = str(id_count)
    id_count += 1
    return str(id_count - 1)

def fmt_time(time, fmt="%H:%M:%S"):
    return datetime.utcfromtimestamp(time / 1000).strftime(fmt)

def fmt_buf(x):
    return "\n".join([sys_prompt.format(time=fmt_time(last_time)), *["".join(x) for x in buf[:x]]])

def flush_buf(x):
    global buf, ids, id_count, first_time
    if buf[:x]:
        print(json.dumps({"text": fmt_buf(x)}))
    buf = buf[x:]
    ids = {}
    id_count = 0
    a = None
    if len(buf) > 0: 
        if buf[-1][1]: buf[-1][1] = " 0"
        if buf[-1][2]: buf[-1][2] = ""
        id_count = 1
        a = buf[-1]
        del buf[-1]
        user_msg(user, first_time, "/login " + user)
        system_msg(first_time, "Successfully logged you in to Discord as User " + user)
        buf.append(a)
    first_time = last_time if a else 0

def tokens():
    return len(sp.Encode(fmt_buf(len(buf))))

def escape(s):
    return s.replace("\n", "\n\t")

def user_msg(usr, time, msg, guild=None, channel=None, id=None, reference=None, attachments=None):
    diffg = '!' if guild != cur_guild else ''
    diffc = '!' if channel != cur_channel else ''
    if user == usr or reauser == usr:
        diffg = ""
        diffc = ""
    if usr == reauser:
        usr = user
    g = " (" + diffg + guild + ")" if guild else ""
    c = " [" + diffc + channel + "]" if channel else ""
    i = " " + id_convert(id) if id else ""
    try: r = " @" + ids[reference] if reference else ""
    except KeyError: r = ""
    a = "\n\t" + "\n\t".join([f"<Attachment {x}>" for x in attachments]) if attachments else ""
    buf.append([f"<{usr} {fmt_time(time)}{g}{c}", i, r, f" > {msg}{a}"])
    if tokens() > MAX_TOKENS: flush_buf(-1)

def system_msg(time, msg):
    user_msg("Discord", time, msg)

for o in obj:
    d = o["data"]
    last_time = d["timestamp"] if "timestamp" in d else o["timestamp"]
    if first_time == 0: first_time = last_time

    if o["action"] == "login":
        cur_guild = ""
        cur_channel = ""
        flush_buf(len(buf))
        login_time = o["timestamp"]
        #user = d["user"]
        user = rand_user()
        reauser = d["user"]
        user_msg(user, login_time, "/login " + user)
        system_msg(login_time, "Successfully logged you in to Discord as User " + user)

    elif o["action"] == "switch-guild":
        new_guild = o["data"]["guild"]
        new_guild_d = o

    elif o["action"] == "switch-channel":
        new_channel = o["data"]["channel"]
        new_channel_d = o

    elif o["action"] == "switch-dm":
        new_guild = "Direct messages" if o["data"]["type"] == "dm" else "Group messages"
        new_channel = o["data"]["channel"]
        new_channel_d = o

    elif o["action"] == "message":
        old_guild = cur_guild
        if new_guild and new_guild != cur_guild:
            if new_guild != "Direct messages" and new_guild != "Group messages":
                if new_guild not in "\n".join(["".join(x) for x in buf]) or (new_channel and new_channel != cur_channel and new_channel_d["data"]["channel"]["unread"] and new_channel_d["data"]["channel"]["mentions"] == 0):
                    user_msg(user, new_guild_d["timestamp"], "/list-guilds", cur_guild, cur_channel)
                    system_msg(new_guild_d["timestamp"], "List of guilds: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in new_guild_d["data"]["guilds"]]))
                user_msg(user, new_guild_d["timestamp"], "/switch-guild " + new_guild, cur_guild, cur_channel)
                system_msg(new_guild_d["timestamp"], "Successfully switched you to guild " + new_guild)
            cur_guild = new_guild
            cur_channel = ""

        if new_channel and new_channel != cur_channel:
            if cur_guild == "Direct messages":
                if new_channel not in "\n".join(["".join(x) for x in buf]):
                    dms = [x for x in new_channel_d["data"]["dms"] if x["type"] == "dm"]
                    user_msg(user, new_channel_d["timestamp"], "/list-dms", old_guild, cur_channel)
                    system_msg(new_channel_d["timestamp"], "List of DMs: " + "\n\t".join([f"{x['name']} ({x['status'] or 'offline'}){' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in dms]))
                user_msg(user, new_channel_d["timestamp"], "/switch-dm " + new_channel, old_guild, cur_channel)
                system_msg(new_channel_d["timestamp"], "Successfully switched you to Direct Message " + new_channel)
            elif cur_guild == "Group messages":
                if new_channel not in "\n".join(["".join(x) for x in buf]):
                    groups = [x for x in new_channel_d["data"]["dms"] if x["type"] == "group"]
                    user_msg(user, new_channel_d["timestamp"], "/list-groups", cur_guild, cur_channel)
                    system_msg(new_channel_d["timestamp"], "List of Groups: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in groups]))
                user_msg(user, new_channel_d["timestamp"], "/switch-group " + new_channel, cur_guild, cur_channel)
                system_msg(new_channel_d["timestamp"], "Successfully switched you to Group " + new_channel)
            else:
                if new_channel not in "\n".join(["".join(x) for x in buf]) or (new_channel_d["data"]["channel"]["unread"] and new_channel_d["data"]["channel"]["mentions"] == 0):
                    user_msg(user, new_channel_d["timestamp"], "/list-channels", cur_guild, cur_channel)
                    system_msg(new_channel_d["timestamp"], f"List of Channels in {cur_guild}: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in new_channel_d["data"]["channels"]]))
                user_msg(user, new_channel_d["timestamp"], "/switch-channel " + new_channel, cur_guild, cur_channel)
                system_msg(new_channel_d["timestamp"], "Successfully switched you to Channel " + new_channel)
            cur_channel = new_channel
            for msg in new_channel_d["data"]["msgs"]:
                user_msg(msg["author"], msg["timestamp"], escape(msg["content"]), cur_guild, cur_channel, msg["id"], msg["reference"] if "reference" in msg else None, msg["attachments"])

        if "fake" not in d: user_msg(d["author"], d["timestamp"], escape(d["content"]), d["guild"] or ("Direct messages" if d["type"] == "dm" else "Group messages"), d["channel"], d["id"], d["reference"] if "reference" in d else None, d["attachments"]) 

    elif o["action"] == "switch-friends":
        user_msg(user, o["timestamp"], "/list-friends", cur_guild, cur_channel)
        system_msg(o["timestamp"], "List of friends: " + "\n\t".join([f"{x['name']} ({x['status']})" for x in o["data"]]))

    elif o["action"] == "edit":
        # this has to be uhh sneeded like we have to do the same id replace thing as in user_msg u know
        # FIXME
        if not d["content"]: continue
        try: system_msg(o["timestamp"], f"Message {ids[o['data']['id']]} Edited to: {escape(o['data']['content'])}")
        except KeyError: pass

flush_buf(len(buf))
