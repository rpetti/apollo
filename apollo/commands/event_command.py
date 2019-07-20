import arrow
from discord.ext import commands

from apollo.can import Can
from apollo.embeds.time_zone_embed import TimeZoneEmbed
from apollo.services import SendChannelSelect
from apollo.models import Event, EventChannel, Guild
from apollo.queries import find_or_create_guild
from apollo.queries import find_or_create_user
from apollo.time_zones import ISO_TIME_ZONES
from apollo.translate import t


class EventCommand(commands.Cog):
    MAX_CAPACITY = 40
    MAX_DESC_LENGTH = 1000
    MAX_TITLE_LENGTH = 200

    TIME_ZONE_INVITE = "https://discord.gg/PQXA2ys"

    def __init__(self, bot, list_events, sync_event_channels):
        self.bot = bot
        self.list_events = list_events
        self.sync_event_channels = sync_event_channels

    @commands.command()
    @commands.guild_only()
    async def event(self, ctx):
        """Create a new event"""
        # Clean up event channels that may have been deleted
        # while the bot was offline.
        self.sync_event_channels.call(ctx.guild.id)

        with self.bot.scoped_session() as session:
            guild = find_or_create_guild(session, ctx.guild.id)

        if not Can(ctx.author, guild).event():
            return await ctx.send(t("error.missing_permissions"))

        with self.bot.scoped_session() as session:
            event_channels = (
                session.query(EventChannel).filter_by(guild_id=ctx.guild.id).all()
            )
            user = find_or_create_user(session, ctx.author.id)

        event = Event()
        event.title = await self._get_title_from_user(ctx)
        event.description = await self._get_desc_from_user(ctx)
        event.organizer = user
        event.capacity = await self._get_capacity_from_user(ctx)
        event.event_channel = await self._get_event_channel(ctx, event_channels)
        event.time_zone = await self._get_time_zone(ctx)
        event.start_time = await self._get_start_time(ctx, event.time_zone)

        channel = self.bot.get_channel(event.event_channel.id)
        await ctx.author.send(t("event.created").format(channel.mention))

        with self.bot.scoped_session() as session:
            session.add(event)

        with self.bot.scoped_session() as session:
            events = (
                session.query(Event)
                .filter_by(event_channel_id=event.event_channel_id)
                .all()
            )

        await self.list_events.call(events, channel)

    async def _choose_event_channel(self, ctx, event_channels):
        message = await SendChannelSelect(
            self.bot, ctx.author.dm_channel, event_channels
        ).call()

        def reaction_check(reaction, user):
            return (message.id == reaction.message.id) and (user.id == ctx.author.id)

        reaction, _ = await self.bot.wait_for(
            "reaction_add", check=reaction_check, timeout=90.0
        )

        return event_channels[int(reaction.emoji[0]) - 1]

    async def _get_capacity_from_user(self, ctx):
        """Retrieve the event capacity from the user"""
        await ctx.author.send(t("event.capacity_prompt"))
        while True:
            resp = (await self.bot.get_next_pm(ctx.author)).content
            if resp.upper() == "NONE":
                return None
            elif resp.isdigit() and int(resp) in range(1, self.MAX_CAPACITY + 1):
                return int(resp)
            else:
                await ctx.author.send(
                    t("event.invalid_capacity").format(self.MAX_CAPACITY)
                )

    async def _get_desc_from_user(self, ctx):
        """Retrieve the event description from the user"""
        await ctx.author.send(t("event.description_prompt"))
        while True:
            resp = (await self.bot.get_next_pm(ctx.author, timeout=240)).content
            if resp.upper() == "NONE":
                return None
            elif len(resp) <= self.MAX_DESC_LENGTH:
                return resp
            else:
                await ctx.author.send(
                    t("event.invalid_description").format(self.MAX_DESC_LENGTH)
                )

    async def _get_event_channel(self, ctx, event_channels):
        """Find or create the event channel for the current guild"""
        if len(event_channels) == 1:
            return event_channels[0]
        elif len(event_channels) > 1:
            return await self._choose_event_channel(ctx, event_channels)
        else:
            channel = await self.bot.create_discord_event_channel(
                ctx.guild, ctx.channel.category
            )
            return EventChannel(id=channel.id, guild_id=ctx.guild.id)

    async def _get_start_time(self, ctx, iso_time_zone):
        """Retrieve a datetime UTC object from the user"""
        await ctx.author.send(t("event.start_time_prompt"))
        while True:
            start_time_str = (await self.bot.get_next_pm(ctx.author)).content
            try:
                utc_start_time = (
                    arrow.get(
                        start_time_str,
                        ["YYYY-MM-DD h:mm A", "YYYY-MM-DD HH:mm", "DD/MM/YYYY HH:mm"],
                        tzinfo=iso_time_zone,
                    )
                    .to("utc")
                    .datetime
                )

                if utc_start_time < arrow.utcnow():
                    await ctx.author.send(t("event.start_time_in_the_past"))
                else:
                    return utc_start_time
            except:
                await ctx.author.send(t("event.invalid_start_time"))

    async def _get_time_zone(self, ctx):
        """Retrieve a valid time zone string from the user"""
        await ctx.author.send(embed=TimeZoneEmbed().call())
        while True:
            resp = (await self.bot.get_next_pm(ctx.author)).content
            if self._valid_time_zone_input(resp):
                time_zone_index = int(resp) - 1
                if time_zone_index in range(len(ISO_TIME_ZONES)):
                    return ISO_TIME_ZONES[time_zone_index]
            else:
                await ctx.author.send(t("event.invalid_time_zone"))

    async def _get_title_from_user(self, ctx):
        """Retrieve the event title from the user"""
        await ctx.author.send(t("event.title_prompt"))
        while True:
            title = (await self.bot.get_next_pm(ctx.author)).content
            if len(title) <= self.MAX_TITLE_LENGTH:
                return title
            else:
                await ctx.author.send(
                    t("event.invalid_title").format(self.MAX_TITLE_LENGTH)
                )

    def _valid_time_zone_input(self, value):
        return value.isdigit() and int(value) in range(1, len(ISO_TIME_ZONES) + 1)
