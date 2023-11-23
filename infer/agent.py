from datetime import datetime
import asyncio
import random
import re

class Agent():
    def __init__(self, ai, name, typing, send):
        self.ai = ai
        self.name = name
        self.typing = typing
        self.send = send
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
        return "\n".join([self.sys_prompt.format(time=self.fmt_time(datetime.now())), *["".join([fmt(x, i) for i, x in enumerate(c)]) for c in self.log]])

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
        c = " (" + diffc + channel + ")" if channel else ""
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
            self.event.set()
            await asyncio.sleep(random.randrange(900, 2700))

    async def task(self, event):
        while True:
            await event.wait()
            event.clear()
            if await self.should_respond(): await self.respond()

    async def should_respond(self):
        # this would be brokey if someone else's username starts with the same token as the bot
        # also i think we wanna increase these chances, maybe especially if we're in a dm or got mentioned
        prompt = self.fmt_log() + "\n<"
        r = await self.ai.completion(prompt, n_probs=5, n_predict=1)
        for prob in r[0]["completion_probabilities"][0]["probs"]:
            if self.name.startswith(prob["tok_str"]):
                p = prob["prob"]
                if p < 0.2: return self.chance(0.05)
                elif p < 0.4: return self.chance(p + 0.4)
                else: return self.chance(p + 0.3)

        return False

    async def respond(self):
        print("responding...")
        err = self.typing(self.cur_guild, self.cur_channel)
        async def x():
            prompt = self.fmt_log() + f"\n<{self.name} " 
            d = await self.ai.completion(prompt, stop=[" ("])
            r = "".join([x["content"] for x in d])
            p = self.parse_msg(r)
            time = p["time"] if p and "time" in p else None
            if time: await self.wait_until(time)
            g = " (" + self.cur_guild + ")" if self.cur_guild else ""
            c = " (" + self.cur_channel + ")" if self.cur_channel else ""
            prompt = self.fmt_log() + f"\n<{self.name} {self.fmt_time(datetime.now())}{g}{c}"
            d = await self.ai.completion(prompt, stop=["\n<", "\n\t<Attachment"])
            r = "".join([x["content"] for x in d])
            p = self.parse_msg(r)
            return p
        if isinstance(err, str):
            p = await x()
        else:
            async with err: p = await x()
        print("bro", p)
        await self.run(p)

    async def wait_until(self, time):
        try:
            date = datetime.strptime(time, "%H:%M:%S")
            diff = datetime.now() - date
            await asyncio.wait_for(self.event.wait(), diff.total_seconds())
        except:
            pass

    async def run(self, p):
        if p["content"][0] == "/":
            await self.add_msg(self.name, datetime.now(), p["content"], self.cur_guild, self.cur_channel)
            await self.run_cmd(p["content"][1:].split())
            if await self.should_respond(): await self.respond()
        else:
            try:
                ref = self.ids[p["reference"]]
            except KeyError:
                ref = None
            err = self.send(self.cur_guild, self.cur_channel, ref, p["content"])
            if isinstance(err, str):
                await self.add_msg(self.name, datetime.now(), p["content"], self.cur_guild, self.cur_channel)
                await self.add_msg("Discord", datetime.now(), err)
                await self.respond()
            else:
                await err

    async def run_cmd(self, cmd):
        print(cmd, self.fmt_log())

    def parse_msg(self, gen):
        r = re.search(r" *(\d+:\d+:\d+)?( \(.*\))?( \[.*\])?( \d+)?( @\d+)? > (.*)", gen)
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
