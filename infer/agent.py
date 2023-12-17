from datetime import datetime
import pytz
import asyncio
import random
import re

class Agent():
    def __init__(self, ai, name, wrap):
        self.ai = ai
        self.name = name
        self.discord = wrap
        self.log = []
        self.cur_guild = ""
        self.cur_channel = ""
        self.ids = {}
        self.id_count = 0
        self.event = asyncio.Event()
        self.sys_prompt = "Welcome to Discord, it is {time}, following commands are available:\n/login <username>\n/switch-guild <guild>\n/switch-channel <channel>\n/switch-dm <user>\n/switch-group <group>\n/list-guilds\n/list-channels\n/list-dms\n/list-groups\n/list-friends\nAny other commands will not work, Have fun!\n<" + name + " 00:00:00 > /login " + name + "\n<Discord 00:00:00 > Successfully logged you in to Discord as User " + name

    def convert_id(self, id):
        self.ids[id] = str(self.id_count)
        self.id_count += 1
        return id

    def fmt_time(self, time, fmt="%H:%M:%S"):
        return time.strftime(fmt)

    def fmt_log(self):
        def fmt(x, i):
            try:
                if i == 1: return " " + self.ids[x]
                elif i == 2: return " @" + self.ids[x]
                else: return x
            except KeyError: return ""
        return "\n".join([self.sys_prompt.format(time=self.fmt_time(datetime.now(pytz.utc))), *["".join([fmt(x, i) for i, x in enumerate(c)]) for c in self.log]])

    async def trim_log(self):
        while len(await self.ai.tokenize(self.fmt_log())) > 4000:
            self.log = self.log[1:]
            self.id_count -= 1
            for k in self.ids.keys(): self.ids[k] -= 1

    async def add_msg(self, author, time, content, guild=None, channel=None, id=None, reference=None, attachments=None):
        # this should be in a lock methinks
        # also if we r switching to new guild AND channel, i dont think we would want a message to come between it
        # so somehow dont do that
        diffg = "!" if guild != self.cur_guild else ""
        diffc = "!" if channel != self.cur_channel else ""
        g = " (" + diffg + guild + ")" if guild else ""
        c = " [" + diffc + channel + "]" if channel else ""
        if id: self.convert_id(id)
        a = "\n\t" + "\n\t".join([f"<Attachment {x}>" for x in attachments]) if attachments else ""
        self.log.append([f"<{author} {self.fmt_time(time)}{g}{c}", id, reference, f" > {content}{a}"])
        await self.trim_log()
        print(self.fmt_log())

    async def signal(self):
        self.event.set()

    async def start(self):
        asyncio.create_task(self.task(self.event))
        asyncio.create_task(self.periodic())

    async def periodic(self):
        while True:
            self.sneed=True
            self.event.set()
            await asyncio.sleep(random.randrange(900, 2700))

    async def task(self, event):
        while True:
            await event.wait()
            event.clear()
            if self.sneed or await self.should_respond(): await self.respond()
            self.sneed = False

    async def should_respond(self):
        # this would be brokey if someone else's username starts with the same token as the bot
        # also i think we wanna increase these chances, maybe especially if we're in a dm or got mentioned
        prompt = self.fmt_log() + "\n<"
        r = await self.ai.completion(prompt, n_probs=5, n_predict=1)
        print("PROB:",prompt)
        for prob in r[0]["completion_probabilities"][0]["probs"]:
            print(prob)
            if self.name.startswith(prob["tok_str"]):
                p = prob["prob"]
                if p < 0.2: return self.chance(0.05)
                elif p < 0.4: return self.chance(p + 0.4)
                else: return self.chance(p + 0.3)

        return False

    async def respond(self):
        print("responding...")
        err = self.discord.typing(self.cur_guild, self.cur_channel)
        async def x():
            prompt = self.fmt_log() + f"\n<{self.name} " 
            d = await self.ai.completion(prompt, stop=[" (", " >"])
            r = "".join([x["content"] for x in d])
            p = self.parse_msg(r)
            time = p["time"] if p and "time" in p else None
            if time: await self.wait_until(time)
            g = " (" + self.cur_guild + ")" if self.cur_guild else ""
            c = " [" + self.cur_channel + "]" if self.cur_channel else ""
            prompt = self.fmt_log() + f"\n<{self.name} {self.fmt_time(datetime.now(pytz.utc))}{g}{c}"
            if not self.cur_channel or not self.cur_guild: prompt = prompt + " >"
            print("DIE", prompt)
            d = await self.ai.completion(prompt, stop=["\n<", "\n\t<Attachment"])
            r = "".join([x["content"] for x in d]).strip()
            p = self.parse_msg(r)
            if not p: p = {"content": r}
            if self.cur_guild: p["guild"] = self.cur_guild
            if self.cur_channel: p["channel"] = self.cur_channel
            if p["content"][:2] == "> ": p["content"] = p["content"][2:].strip()
            print("SIR", p["content"])
            return p
        if isinstance(err, str):
            p = await x()
        else:
            async with err: p = await x()
        print("bro", p)
        await self.run(p)

    async def wait_until(self, time):
        try:
            date = datetime.strptime(time, "%H:%M:%S").replace(tzinfo=pytz.utc)
            diff = datetime.now(pytz.utc) - date
            await asyncio.wait_for(self.event.wait(), diff.total_seconds())
        except:
            pass

    async def run(self, p):
        if "content" not in p: return
        if p["content"][0] == "/":
            await self.add_msg(self.name, datetime.now(pytz.utc), p["content"], self.cur_guild, self.cur_channel)
            x = p["content"][1:].split(" ", 1)
            await self.run_cmd(x[0], x[1] if len(x) > 1 else None)
            await self.respond()
            #if await self.should_respond(): await self.respond()
        else:
            try:
                ref = self.ids[p["reference"]]
            except KeyError:
                ref = None
            err = self.discord.send(self.cur_guild, self.cur_channel, ref, p["content"].replace("\n\t", "\n"))
            if isinstance(err, str):
                await self.add_msg(self.name, datetime.now(pytz.utc), p["content"], self.cur_guild, self.cur_channel)
                await self.add_msg("Discord", datetime.now(pytz.utc), err)
                await self.respond()
            else:
                await err

    async def add_history(self):
        for x in await self.discord.channel_history(self.cur_guild, self.cur_channel):
            await self.add_msg(**x)

    async def run_cmd(self, cmd, rest):
        match cmd:
            case "switch-guild": 
                if self.discord.guild_exists(rest):
                    self.cur_guild = rest
                    self.cur_channel = None
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Successfully switched you to guild {rest}")
                    await self.add_msg(self.name, datetime.now(pytz.utc), "/list-channels")
                    try:
                        await self.add_msg("Discord", datetime.now(pytz.utc), f"List of Channels in {self.cur_guild}: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in self.discord.get_channels(self.cur_guild)]))
                    except Exception as e:
                        await self.add_msg("Discord", datetime.now(pytz.utc), str(e))
                else:
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Guild {rest or 'None'} does not exist. use /list-guilds to see what guilds you are in.")
            case "switch-channel":
                if self.discord.channel_exists(self.cur_guild, rest):
                    self.cur_channel = rest
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Successfully switched you to Channel {rest}")
                    await self.add_history()
                else:
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Channel {rest or 'None'} does not exist in current guild {self.cur_guild or 'None'}. use /list-channels to see what channels are in the current guild.")
            case "switch-dm":
                if self.discord.dm_exists(rest):
                    self.cur_guild = "Direct messages"
                    self.cur_channel = rest
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Successfully switched you to Direct Message {rest}")
                    await self.add_history()
                else:
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Direct message {rest or 'None'} does not exist. use /list-dms to see all your Direct Messages.")
            case "switch-group":
                if self.discord.group_exists(rest):
                    self.cur_guild = "Group messages"
                    self.cur_channel = rest
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Successfully switched you to Group Message {rest}")
                    await self.add_history()
                else:
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"Group message {rest or 'None'} does not exist. use /list-groups to see all your Group Messages.")
            case "list-guilds":
                await self.add_msg("Discord", datetime.now(pytz.utc), "List of guilds: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in self.discord.get_guilds()]))
            case "list-channels":
                try:
                    await self.add_msg("Discord", datetime.now(pytz.utc), f"List of Channels in {self.cur_guild}: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in self.discord.get_channels(self.cur_guild)]))
                except Exception as e:
                    await self.add_msg("Discord", datetime.now(pytz.utc), str(e))
            case "list-dms":
                await self.add_msg("Discord", datetime.now(pytz.utc), "List of DMs: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in self.discord.get_dms()]))
            case "list-groups":
                await self.add_msg("Discord", datetime.now(pytz.utc), "List of Groups: " + "\n\t".join([f"{x['name']}{' @' + str(x['mentions']) if x['mentions'] > 0 else ''}{' (unread!)' if x['unread'] else ''}" for x in self.discord.get_groups()]))
            case "list-friends":
                await self.add_msg("Discord", datetime.now(pytz.utc), "List of friends: " + "\n\t".join([f"{x['name']} (x['status'])" for x in self.discord.get_friends()]))

    def parse_msg(self, gen):
        r = re.search(r" *(\d+:\d+:\d+)?( \(.*\))?( \[.*\])?( \d+)?( @\d+)? > (.*)", gen, re.MULTILINE)
        if not r: return None
        d = {}
        for capture in r.groups():
            if not capture: continue
            if capture[0] != ' ' and capture[0].isdigit(): d["time"] = capture
            elif capture[0] != ' ': d["content"] = capture
            elif capture[1] == '(': d["guild"] = capture[2:][:-1]
            elif capture[1] == '[': d["channel"] = capture[2:][:-1]
            elif capture[1] == '@': d["reference"] = int(capture[2:])
            else: d["id"] = int(capture[1:])
        return d

    def chance(self, c):
        return random.random() < c
