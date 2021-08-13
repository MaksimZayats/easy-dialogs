from contextvars import ContextVar

from vkbottle import Bot

_bot = ContextVar('bot')


def get_current_bot() -> Bot:
    return _bot.get()


def set_current_bot(bot: Bot) -> None:
    _bot.set(bot)
