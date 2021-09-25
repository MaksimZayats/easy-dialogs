from typing import Callable, List, Optional, Tuple, Type, Union

from aiogram import Dispatcher
from aiogram.dispatcher.handler import SkipHandler
from aiogram.types import CallbackQuery, ContentType
from aiogram.types import Message as AiogramMessage
from aiogram.types.base import TelegramObject

from dialog import bases
from dialog.shared.storage import AiogramBasedScenesStorage
from dialog.telegram.types import EventType


class View:
    @staticmethod
    async def send_new_message(*args, **kwargs) -> List[AiogramMessage]:
        obj: Union[AiogramMessage, CallbackQuery, TelegramObject] = args[0]

        sent_messages: List[AiogramMessage] = []

        try:
            user_id = obj.from_user.id
        except AttributeError:
            user_id = obj.user.id  # NOQA

        try:
            chat_id = obj.chat.id
        except AttributeError:
            try:
                chat_id = obj.message.chat.id
            except AttributeError:
                chat_id = user_id

        scene: 'Scene' = kwargs.get(Dialog.KEY_FOR_CURRENT_SCENES)  # type: ignore

        async for message_to_send in scene.get_messages(*args, **kwargs):
            sent_message = await message_to_send.send(chat_id=chat_id)
            sent_messages.append(sent_message)

        if isinstance(obj, CallbackQuery):
            await obj.answer()

        return sent_messages


class Handler(bases.BaseHandler):
    async def __call__(self, *args, **kwargs):
        """
        It is a function-router.
        Redirects the received update to the desired scene.
        """

        obj: Union[AiogramMessage, CallbackQuery, TelegramObject] = args[0]

        try:
            user_id = obj.from_user.id
        except AttributeError:
            user_id = obj.user.id  # NOQA

        try:
            chat_id = obj.chat.id
        except AttributeError:
            try:
                chat_id = obj.message.chat.id
            except AttributeError:
                chat_id = user_id

        await self.default_handler(handler_args=args, handler_kwargs=kwargs, chat_id=chat_id, user_id=user_id)

    def skip_handler(self):
        raise SkipHandler


class FiltersGroup(bases.BaseFiltersGroup):
    @property
    def default_event_types(self) -> Tuple[str]:
        return EventType.MESSAGE,

    def init(self, dp: Optional[Dispatcher] = None):  # type: ignore
        dp = dp or Dispatcher.get_current()

        for event in self.event_types:
            if event == 'update':
                event_handler = dp.updates_handler
            else:
                event_handler = getattr(dp, f'{event}_handlers')

            if event_handler is None:
                continue

            resolved_filters = dp.filters_factory.resolve(event_handler, **self.filters_as_kwargs)

            filters_to_check = list(self.filters_as_args) + resolved_filters

            self.filters_to_check[event] = [getattr(filter_, 'check', filter_)
                                            for filter_ in filters_to_check]


class Scene(bases.BaseScene):
    filters: FiltersGroup
    relations: Tuple['Relation', ...]

    def init(self, dp: Optional[Dispatcher] = None) -> None:  # type: ignore
        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.filters.init(dp=dp)

        if self.filters:
            self.filters.init(dp=dp)

    @property
    def default_view(self) -> Callable:
        return View.send_new_message


class Relation(bases.BaseRelation):
    filters: FiltersGroup

    @property
    def default_filters_group(self) -> Type[FiltersGroup]:
        return FiltersGroup


class Router(bases.BaseRouter):
    relations: Tuple[Relation, ...]

    def init(self, dp: Optional[Dispatcher] = None):  # type: ignore
        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.filters.init(dp=dp)


class Dialog(bases.BaseDialog):
    @classmethod
    def register_handlers(cls,  # type: ignore
                          dp: Dispatcher,
                          scenes_storage: Optional[bases.BaseScenesStorage] = None,
                          handler: Type[bases.BaseHandler] = Handler):
        cls.scenes_storage = scenes_storage or AiogramBasedScenesStorage(storage=dp.storage)
        cls.init(dp)

        dp.register_message_handler(
            handler(dialog=cls, event_type=EventType.MESSAGE),
            content_types=ContentType.ANY
        )
        dp.register_callback_query_handler(handler(dialog=cls, event_type=EventType.CALLBACK_QUERY))
        dp.register_poll_handler(handler(dialog=cls, event_type=EventType.POLL))
        dp.register_poll_answer_handler(handler(dialog=cls, event_type=EventType.POLL_ANSWER))
        dp.register_channel_post_handler(handler(dialog=cls, event_type=EventType.CHANNEL_POST))
        dp.register_chat_member_handler(handler(dialog=cls, event_type=EventType.CHAT_MEMBER))
        dp.register_chosen_inline_handler(handler(dialog=cls, event_type=EventType.CHOSEN_INLINE_RESULT))
        dp.register_edited_message_handler(handler(dialog=cls, event_type=EventType.EDITED_MESSAGE))
        dp.register_pre_checkout_query_handler(handler(dialog=cls, event_type=EventType.PRE_CHECKOUT_QUERY))
        dp.register_shipping_query_handler(handler(dialog=cls, event_type=EventType.SHIPPING_QUERY))
        dp.register_my_chat_member_handler(handler(dialog=cls, event_type=EventType.MY_CHAT_MEMBER))

        # TODO: register all Events

    @classmethod
    def init(cls, dp: Optional[Dispatcher] = None):  # type: ignore
        for scene in cls.initialized_scenes.values():
            scene.init(dp=dp)

        for router in cls.initialized_routers:
            router.init(dp=dp)
