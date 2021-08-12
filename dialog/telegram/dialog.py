from typing import Any, Awaitable, Callable, List, Optional, Sequence, Union

from aiogram import Dispatcher
from aiogram.dispatcher.filters import AbstractFilter
from aiogram.dispatcher.handler import SkipHandler
from aiogram.dispatcher.storage import BaseStorage
from aiogram.types import CallbackQuery
from aiogram.types import Message as AiogramMessage
from aiogram.types.base import TelegramObject

from dialog import bases, defaults
from dialog.utils import run_function

from .types import EventType


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

        scene: 'Scene' = kwargs.get(Dialog.KEYS_FOR_CURRENT_SCENES[0])

        async for message_to_send in scene.get_messages(*args, **kwargs):
            sent_message = await message_to_send.send(chat_id=chat_id)
            sent_messages.append(sent_message)

        if isinstance(obj, CallbackQuery):
            await obj.answer()

        return sent_messages


class AiogramBasedScenesStorage(bases.BaseScenesStorage):
    def __init__(self,
                 aiogram_storage: BaseStorage,
                 data_key: str = 'scenes_history'):
        self.storage = aiogram_storage
        self.data_key = data_key

    async def get_scenes_history(self, *,
                                 chat_id: Union[int, str],
                                 user_id: Union[int, str]) -> List[str]:
        data = await self.storage.get_data(chat=chat_id, user=user_id)
        return data.get(self.data_key, [])

    async def update_scenes_history(self, *,
                                    chat_id: Union[int, str],
                                    user_id: Union[int, str],
                                    new_scenes_history: Sequence[str]) -> Sequence[str]:
        await self.storage.update_data(chat=chat_id, user=user_id,
                                       **{self.data_key: new_scenes_history})

        return new_scenes_history

    async def set_current_scene(self, *,
                                chat_id: Union[int, str],
                                user_id: Union[int, str],
                                new_scene: 'Scene') -> Sequence[str]:
        data = await self.storage.get_data(chat=chat_id, user=user_id)

        scenes_history: List[str] = data.get(self.data_key, [])
        try:
            if scenes_history[-1] != new_scene.full_name:
                scenes_history.append(new_scene.full_name)
        except IndexError:
            scenes_history.append(new_scene.full_name)

        await self.storage.update_data(
            chat=chat_id, user_id=user_id,
            **{self.data_key: scenes_history})

        return scenes_history


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

        previous_scene = await Dialog.scenes_storage.get_previous_scene(user_id=user_id, chat_id=chat_id)
        current_scene = await Dialog.scenes_storage.get_current_scene(user_id=user_id, chat_id=chat_id)

        while True:  # While to skip transitional scenes
            for key in Dialog.KEYS_FOR_PREVIOUS_SCENES:
                kwargs[key] = previous_scene

            for key in Dialog.KEYS_FOR_CURRENT_SCENES:
                kwargs[key] = current_scene

            for key in Dialog.KEYS_FOR_NEXT_SCENES:
                kwargs[key] = None

            next_scene = await Dialog.scenes_storage.get_next_scene(
                current_scene=current_scene, current_event_type=self.event_type,
                handler_args=args, handler_kwargs=kwargs)

            if next_scene is None:
                raise SkipHandler

            if current_scene:
                for key in Dialog.KEYS_FOR_NEXT_SCENES:
                    kwargs[key] = next_scene

                for on_exit_function in current_scene.on_exit:
                    await run_function(on_exit_function, *args, **kwargs)

                for key in Dialog.KEYS_FOR_NEXT_SCENES:
                    kwargs[key] = None

            if next_scene.can_stay and current_scene != next_scene:
                await Dialog.scenes_storage.set_current_scene(
                    chat_id=chat_id, user_id=user_id, new_scene=next_scene)

            for key in Dialog.KEYS_FOR_PREVIOUS_SCENES:
                kwargs[key] = current_scene

            for key in Dialog.KEYS_FOR_CURRENT_SCENES:
                kwargs[key] = next_scene

            for on_entry_function in next_scene.on_enter:
                await run_function(on_entry_function, *args, **kwargs)

            await run_function(next_scene.view, *args, **kwargs)

            if not next_scene.is_transitional_scene:
                break

            previous_scene, current_scene = current_scene, next_scene


class Scene(bases.BaseScene):
    def init(self, dp: Optional[Dispatcher] = None) -> None:
        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.init_filters(dp=dp)

    @property
    def default_view(self) -> Callable:
        return View.send_new_message


class Relation(bases.BaseRelation):
    def __init__(self,
                 to: Union[bases.BaseScene, str, defaults.FutureScene,
                           Callable[..., bases.BaseScene],
                           Callable[..., Awaitable[bases.BaseScene]]],
                 *filters_as_args: Union[Callable[..., bool],
                                         Callable[..., Awaitable[bool]],
                                         AbstractFilter],
                 event_types: Union[str, Sequence[str]] = (EventType.MESSAGE, ),
                 on_transition: Union[Callable, Sequence[Callable]] = tuple(),
                 **filters_as_kwargs: Any
                 ):
        super().__init__(to, *filters_as_args, event_types=event_types,
                         on_transition=on_transition, **filters_as_kwargs)

    def init_filters(self, dp: Optional[Dispatcher] = None):
        dp = dp or Dispatcher.get_current()

        for event in self.event_types:
            if event == 'update':
                event_handler = dp.updates_handler
            else:
                event_handler = getattr(dp, f'{event}_handlers')

            if event_handler is None:
                continue

            _filters_as_kwargs = self._filters_as_kwargs.copy()

            not_registered_filters: List[str] = []

            while True:
                try:
                    filters = dp.filters_factory.resolve(event_handler, **_filters_as_kwargs)

                    if not_registered_filters:
                        print(f'Scene "{self.to_scene.full_name}", '
                              f"filter(s): {', '.join(not_registered_filters)}; Not registered.")
                    break
                except NameError as e:
                    incorrect_filter_name = str(e).split(' ')[-1].replace("'", "")
                    _filters_as_kwargs.pop(incorrect_filter_name)
                    not_registered_filters.append(incorrect_filter_name)

            self.filters[event] = [filter_.check for filter_ in filters] + \
                                  [getattr(filter_, 'check', filter_) for filter_ in self._filters_as_args]


class Router(bases.BaseRouter):
    def init(self, dp: Optional[Dispatcher] = None):
        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.init_filters(dp)


class Dialog(bases.BaseDialog):
    @classmethod
    def register(cls,
                 dp: Dispatcher,
                 scenes_storage: Optional[bases.BaseScenesStorage] = None,
                 handler: Callable[..., Callable[..., Awaitable]] = Handler):
        cls.scenes_storage = scenes_storage or AiogramBasedScenesStorage(aiogram_storage=dp.storage)
        cls.init(dp)

        dp.register_message_handler(handler(event_type=EventType.MESSAGE))
        dp.register_callback_query_handler(handler(event_type=EventType.CALLBACK_QUERY))
        dp.register_poll_handler(handler(event_type=EventType.POLL))
        dp.register_poll_answer_handler(handler(event_type=EventType.POLL_ANSWER))
        dp.register_channel_post_handler(handler(event_type=EventType.CHANNEL_POST))
        dp.register_chat_member_handler(handler(event_type=EventType.CHAT_MEMBER))
        dp.register_chosen_inline_handler(handler(event_type=EventType.CHOSEN_INLINE_RESULT))
        dp.register_edited_message_handler(handler(event_type=EventType.EDITED_MESSAGE))
        dp.register_pre_checkout_query_handler(handler(event_type=EventType.PRE_CHECKOUT_QUERY))
        dp.register_shipping_query_handler(handler(event_type=EventType.SHIPPING_QUERY))
        dp.register_my_chat_member_handler(handler(event_type=EventType.MY_CHAT_MEMBER))

        # TODO: register all Events

    @classmethod
    def init(cls, dp: Optional[Dispatcher] = None):
        for scene in cls.initialized_scenes.values():
            scene.init(dp=dp)

        for router in cls.initialized_routers:
            router.init(dp=dp)
