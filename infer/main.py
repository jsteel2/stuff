from ai import AI
from agent import Agent
import selfcord
import os

class Client(selfcord.Client):
    async def on_ready(self):
        ai = AI("8.218.148.93", "7860", remote=True)
        self.messages = {}
        #ai = AI("cock-q6_k.gguf", "6969")
        await ai.init()
        self.agent = Agent(ai, self.user.name, self.typing, self.send)
        await self.agent.start()
        print("Logged in as", self.user)

    def typing(self, guild, channel):
        try:
            return self.channel_from(guild, channel).typing()
        except Exception as e:
            return str(e)

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
        elif guild_name == "Group Messages":
            channel = [x for x in self.private_channels if isinstance(x, selfcord.GroupChannel) and ", ".join([x.name for x in x.recipients]) == channel_name]
            if channel: return channel[0]
            else: raise Exception(f"Group message {channel_name or 'None'} does not exist. use /list-groups to see all your Group Messages.")
        guild = [x for x in self.guilds if x.name == guild_name]
        if guild: guild = guild[0]
        else: raise Exception(f"Guild {guild_name or 'None'} does not exist. use /list-guilds to see what guilds you are in.")
        channel = [x for x in guild.channels if x.name == channel_name and isinstance(x, selfcord.TextChannel)]
        if channel: return channel[0]
        else: raise Exception(f"Channel {channel_name or 'None'} does not exist in current guild {guild_name or 'None'}. use /list-channels to see what channels are in the current guild.")

    async def on_message(self, message: selfcord.Message):
        #if message.author == self.user: return

        if message.guild and not message.channel.permissions_for(message.guild.get_member(self.user.id)).send_messages: return

        if self.user in message.mentions or isinstance(message.channel, selfcord.DMChannel):
            if message.guild: guild = message.guild.name
            elif isinstance(message.channel, selfcord.GroupChannel): guild = "Group messages"
            else: guild = "Direct messages"
            if getattr(message.channel, "name", None): channel = message.channel.name
            elif getattr(message.channel, "recipients", None): channel = ", ".join([x.name for x in message.channel.recipients])
            else: channel = message.channel.recipient.name
            self.messages[message.id] = message
            await self.agent.add_msg(message.author.name, message.created_at, message.content, guild, channel, message.id, message.reference, [x.filename for x in message.attachments])
            await self.agent.signal()

if __name__ == "__main__":
    Client().run(os.getenv("TOKEN"))
