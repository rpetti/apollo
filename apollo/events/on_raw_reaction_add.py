from apollo import emojis as emoji
from apollo.list_events import list_events, update_event_message
from apollo.models import Event, Response
from apollo.queries import find_event_from_message, \
    find_or_create_response


class OnRawReactionAdd:
    ACCEPTED  = 'accepted'
    ALTERNATE = 'alternate'
    DECLINED  = 'declined'

    emoji_statuses = {
        emoji.CHECK: ACCEPTED,
        emoji.QUESTION: ALTERNATE,
        emoji.CROSS: DECLINED
    }

    def __init__(self, bot):
        self.bot = bot


    async def on_raw_reaction_add(self, payload):
        session = self.bot.Session()

        # Ignore reactions added by the bot
        if payload.user_id == self.bot.user.id:
            return

        event = find_event_from_message(session, payload.message_id)
        if event:
            await self._handle_event_reaction(session, event, payload)

        session.commit()


    def _save_response(self, event, payload):
        session = self.bot.Session()

        response = find_or_create_response(
            session,
            payload.user_id,
            event.id
        )
        response.status = self.emoji_statuses.get(payload.emoji.name)

        session.add(response)
        session.commit()


    async def _handle_event_reaction(self, session, event, payload):
        if self.emoji_statuses.get(payload.emoji.name):
            self._save_response(event, payload)
            await update_event_message(self.bot, event.id)
            await self.bot.remove_reaction(payload)
            session.add(event)
        elif payload.emoji.name == emoji.SKULL:
            session.delete(event)
            await list_events(self.bot, event.event_channel.id)