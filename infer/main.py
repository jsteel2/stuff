from ai import AI
from agent import Agent
import selfcord
import pytz
from datetime import datetime
import os

# FIXME: group dms can have names

class Client(selfcord.Client):
    async def on_ready(self):
        ai = AI("8.218.148.93", "7860", remote=True)
        self.messages = {}
        #ai = AI("cock-q6_k.gguf", "6969")
        await ai.init()
        self.agent = Agent(ai, self.user.name, self)
        await self.agent.start()
        print("Logged in as", self.user)

    def typing(self, guild, channel):
        try:
            return self.channel_from(guild, channel).typing()
        except Exception as e:
            return str(e)

    async def channel_history(self, guild, channel):
        try:
            nchannel = self.channel_from(guild, channel)
            r = []
            async for x in nchannel.history(limit=20):
                r.append({"author": x.author, "time": x.created_at, "content": x.content, "guild": guild, "channel": channel, "id": x.id, "reference": x.reference.message_id if x.reference else None, "attachments": [x.filename for x in x.attachments]})
            return r[::-1]
        except Exception as e:
            return [{"author": "Discord", "time": datetime.now(pytz.utc), "content": str(e)}]

    def get_guilds(self):
        # TODO: add unreads, also do mentions even work like this in a selfbot?
        mentions = lambda x: sum([x.mention_count for x in x.channels if isinstance(x, selfcord.TextChannel)])
        return [{"name": x.name, "mentions": mentions(x), "unread": mentions(x)} for x in self.guilds]

    def get_channels(self, guild_name):
        guild = [x for x in self.guilds if x.name == guild_name]
        if guild: guild = guild[0]
        else: raise Exception(f"Guild {guild_name or 'None'} does not exist. use /list-guilds to see what guilds you are in.")
        return [{"name": x.name, "mentions": x.mention_count, "unread": x.mention_count} for x in guild.channels if isinstance(x, selfcord.TextChannel)]

    def get_dms(self):
        return [{"name": x.recipient.name, "mentions": x.mention_count, "unread": x.mention_count} for x in self.private_channels if isinstance(x, selfcord.DMChannel)]

    def get_groups(self):
        return [{"name": ", ".join([x.name for x in x.recipients]), "mentions": x.mention_count, "unread": x.mention_count} for x in self.private_channels if isinstance(x, selfcord.GroupChannel)]

    def get_friends(self):
        return [{"name": x.user.name, "status": x.raw_status} for x in self.friends]

    def send(self, guild, channel, reference, content):
        try:
            return self.channel_from(guild, channel).send(content, reference=self.messages.get(reference, None))
        except Exception as e:
            return str(e)

    def channel_from(self, guild_name, channel_name):
        if guild_name == "Direct messages":
            channel = [x for x in self.private_channels if isinstance(x, selfcord.DMChannel) and x.recipient.name == channel_name]
            if channel: return channel[0]
            else: raise Exception(f"Direct message {channel_name or 'None'} does not exist. use /list-dms to see all your Direct Messages.")
        elif guild_name == "Group messages":
            channel = [x for x in self.private_channels if isinstance(x, selfcord.GroupChannel) and ", ".join([x.name for x in x.recipients]) == channel_name]
            if channel: return channel[0]
            else: raise Exception(f"Group message {channel_name or 'None'} does not exist. use /list-groups to see all your Group Messages.")
        guild = [x for x in self.guilds if x.name == guild_name]
        if guild: guild = guild[0]
        else: raise Exception(f"Guild {guild_name or 'None'} does not exist. use /list-guilds to see what guilds you are in.")
        channel = [x for x in guild.channels if x.name == channel_name and isinstance(x, selfcord.TextChannel)]
        if channel: return channel[0]
        else: raise Exception(f"Channel {channel_name or 'None'} does not exist in current guild {guild_name or 'None'}. use /list-channels to see what channels are in the current guild.")

    def guild_exists(self, guild_name):
        try:
            self.channel_from(guild_name, None)
        except Exception as e:
            return str(e).startswith("Channel")

    def w(self, g, c):
        try:
            self.channel_from(g, c)
            return True
        except:
            return False

    def channel_exists(self, guild_name, channel_name):
        return self.w(guild_name, channel_name)

    def dm_exists(self, dm_name):
        return self.w("Direct messages", dm_name)

    def group_exists(self, group_name):
        return self.w("Group messages", group_name)

    async def on_message(self, message: selfcord.Message):
        #if message.author == self.user: return

        if message.content == "!wipe":
            self.agent.log=[]
            self.agent.id_count=0
            return

        if message.content.startswith("!sus"):
            l = message.content.split()
            if len(l) > 1: n = " ".join(l[1:])
            else: n = self.user.name
            self.agent.sys_prompt = self.agent.sys_prompt.replace(self.agent.name, n)
            self.agent.name = n
            return

        if message.author.name == self.user.name: messageauthorname = self.agent.name
        else: messageauthorname = message.author.name

        if message.guild and not message.channel.permissions_for(message.guild.get_member(self.user.id)).send_messages and message.content != "!cmere": return
        if message.guild: guild = message.guild.name
        elif isinstance(message.channel, selfcord.GroupChannel): guild = "Group messages"
        else: guild = "Direct messages"
        if getattr(message.channel, "name", None): channel = message.channel.name
        elif getattr(message.channel, "recipients", None): channel = ", ".join([x.name for x in message.channel.recipients])
        else: channel = message.channel.recipient.name

        if message.content == "!cmere":
            self.agent.cur_guild = guild
            self.agent.cur_channel = channel
            return

        if self.user in message.mentions or isinstance(message.channel, selfcord.DMChannel) or self.user == message.author or (guild == self.agent.cur_guild and channel == self.agent.cur_channel):
            self.messages[message.id] = message
            await self.agent.add_msg(messageauthorname, message.created_at, message.content.replace("\n", "\n\t"), guild, channel, message.id, message.reference, [x.filename for x in message.attachments])
            await self.agent.signal()

if __name__ == "__main__":
    Client().run(os.getenv("TOKEN"))
