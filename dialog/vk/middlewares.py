from aiogram.dispatcher.storage import BaseStorage, FSMContext
from vkbottle import BaseMiddleware
from vkbottle.bot import Message


class FSMMiddleware(BaseMiddleware):
    def __init__(self, storage: BaseStorage):
        self.storage = storage

    async def pre(self, message: Message):
        return {"state": FSMContext(storage=self.storage, chat=message.chat_id, user=message.from_id)}
