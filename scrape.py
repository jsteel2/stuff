import selfcord
import sys
import json
import re
import asyncio
import time

token = "Njg2OTczODM0NTk1MDA4NTEy.Gu7mj7.yLfR1q2T6LiA4iIym8YsF11W9fSENtLEmIF_kI"

def log(action, time, **data):
    print(json.dumps({"timestamp": time, "action": action, "data": data}))

class Client(selfcord.Client):
    async def on_ready(self):
        c = self.get_channel(int(sys.argv[1]))
        while True:
            try:
                msgs = []
                async for x in c.history(limit=int(sys.argv[2])):
                    bc = {}
                    async def baller(x):
                        if x in bc: return bc[x]
                        try: r = (await self.fetch_user(x)).name
                        except: r = "Unknown User"
                        bc[x] = r
                        return r
                    users = {x: await baller(x) for x in re.findall(r"<@(\d+)>", x.content)}
                    d = {
                        "author": x.author.name,
                        "attachments": [x.filename for x in x.attachments],
                        "content": re.sub(r"<[@#](\d+)>", lambda x: x.string[:2] + (users.get(x.groups(0)[0], "Unknown User") if x.string[1] == "@" else getattr(self.get_channel(int(x.groups(0)[0])), "name", "Unknown Channel")) + ">", x.content),
                        "timestamp": int(x.created_at.timestamp() * 1000),
                        "id": str(x.id)
                    }
                    if x.reference: d["reference"] = str(x.reference.message_id)
                    msgs.append(d)
                msgs.sort(key=lambda x: x["timestamp"])
                break
            except:
                continue
        t = time.time() - 3 * 1000

        log("login", t, user=self.user.name)

        if isinstance(c, (selfcord.DMChannel, selfcord.GroupChannel)):
            dms = [{
                "name": x.recipient.name if isinstance(x, selfcord.DMChannel) else x.name,
                "type": "dm" if isinstance(x, selfcord.DMChannel) else "group",
                "status": x.recipient.relationship.raw_status if isinstance(x, selfcord.DMChannel) and x.recipient.relationship else None,
                "mentions": x.mention_count,
                "unread": True if x.mention_count > 0 else False
            } for x in self.private_channels]
            log("switch-dm", t + 1 * 1000, msgs=msgs, type="dm" if isinstance(c, selfcord.DMChannel) else "group", dms=dms, channel=c.recipient.name if isinstance(c, selfcord.DMChannel) else c.name)
        else:
            guilds = [{
                "name": x.name,
                "mentions": mentions - 1,
                "unread": True if mentions - 1 > 0 else False
            } for x in self.guilds if (mentions := (sum([x.mention_count for x in x.channels if isinstance(x, selfcord.TextChannel)]) if not x.notification_settings.muted.muted else 0) + 1)]
            channels = [{
                "name": x.name,
                "mentions": m - 1,
                "unread": True if m - 1 > 0 else False
            } for x in c.guild.channels if isinstance(x, selfcord.TextChannel) and (p := x.permissions_for(x.guild.get_member(self.user.id))) and p.send_messages and p.view_channel and (m := (x.mention_count if not x.notification_settings.muted.muted else 0) + 1)]
            log("switch-guild", t + 1 * 1000, guild=c.guild.name, guilds=guilds)
            log("switch-channel", t + 2 * 1000, msgs=msgs, channel=c.name, channels=channels)

        log("message", t + 3 * 1000, fake=True)
        await self.close()

Client().run(token)
