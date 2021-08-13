from typing import Any, Callable, Dict, List, Optional, Type

from aiogram.contrib.fsm_storage.memory import MemoryStorage
from vkbottle import Bot
from vkbottle.bot import Message
from vkbottle.dispatch.handlers import FromFuncHandler

from dialog import bases
from dialog.shared.storage import AiogramBasedScenesStorage
from dialog.shared.utils import run_function
from dialog.vk.types import EventType
from dialog.vk.utils import set_current_bot, get_current_bot


class View:
    @staticmethod
    async def send_new_message(*args, **kwargs):
        obj: Message = args[0]

        sent_messages_ids: List[int] = []

        peer_id = obj.peer_id

        scene: 'Scene' = kwargs.get(Dialog.KEY_FOR_CURRENT_SCENES)

        async for message_to_send in scene.get_messages(*args, **kwargs):
            sent_messages_ids.append(
                await message_to_send.send(peer_id=peer_id))

        return sent_messages_ids


class Handler(bases.BaseHandler):
    async def __call__(self, *args, **kwargs):
        """
        It is a function-router.
        Redirects the received update to the desired scene.
        """
        obj: Message = args[0]

        user_id = obj.from_id
        chat_id = obj.chat_id

        await self.default_handler(handler_args=args, handler_kwargs=kwargs,
                                   chat_id=chat_id, user_id=user_id)

    def skip_handler(self):
        pass


class Scene(bases.BaseScene):
    def init(self, bot: Bot) -> None:
        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.init_filters(bot=bot)

    @property
    def default_view(self) -> Callable:
        return View.send_new_message


class Relation(bases.BaseRelation):
    def init_filters(self, bot: Optional[Bot] = None):
        bot = bot or get_current_bot()

        for event in self.event_types:
            filters_to_check = list(self._filters_as_args) + \
                               bot.labeler.get_custom_rules(self._filters_as_kwargs)

            self.filters[event] = [getattr(filter_, 'check', filter_)
                                   for filter_ in filters_to_check]

    async def check_filters(self,
                            handler_args: tuple,
                            handler_kwargs: Dict[str, Any],
                            event_type: str) -> bool:
        for filter_ in self.filters[event_type]:
            filter_result = await run_function(filter_, *handler_args, **handler_kwargs)

            if isinstance(filter_result, dict):
                handler_kwargs |= filter_result  # added new kwargs from vkbottle rules
            else:
                if not filter_result:
                    return False
        else:
            return True


class Router(bases.BaseRouter):
    def init(self, bot: Bot):
        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.init_filters(bot=bot)


class Dialog(bases.BaseDialog):
    @classmethod
    def register(cls,
                 bot: Bot,
                 scenes_storage: Optional[bases.BaseScenesStorage] = None,
                 handler: Type[bases.BaseHandler] = Handler):
        set_current_bot(bot=bot)

        cls.scenes_storage = scenes_storage or AiogramBasedScenesStorage(storage=MemoryStorage())
        cls.init(bot)

        bot.labeler.message_view.handlers.append(
            FromFuncHandler(handler=handler(dialog=cls, event_type=EventType.MESSAGE), blocking=False))

    @classmethod
    def init(cls, bot: Bot):
        for scene in cls.initialized_scenes.values():
            scene.init(bot=bot)

        for router in cls.initialized_routers:
            router.init(bot=bot)
