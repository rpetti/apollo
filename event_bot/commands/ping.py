from discord.ext import commands

class Ping:

    def __init__(self, bot):
        self.bot = bot


    @commands.command()
    async def ping(self, ctx):
        await ctx.send("Pong!")
