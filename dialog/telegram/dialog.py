from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Optional, Union, Dict, Callable, \
    AsyncIterator, Any, List, Sequence, Set, Awaitable

from aiogram import Dispatcher
from aiogram.dispatcher.filters import AbstractFilter
from aiogram.dispatcher.handler import SkipHandler
from aiogram.dispatcher.storage import BaseStorage
from aiogram.types import Message as AiogramMessage, CallbackQuery
from aiogram.types.base import TelegramObject

from dialog.utils import run_function
from .types import BaseMessage, EventType, FutureScene


class _DialogMeta(type):
    def __new__(mcs, cls_name: str, superclasses: tuple, attributes: dict, **kwargs):
        cls: 'Dialog' = super().__new__(mcs, cls_name, superclasses, attributes)  # type: ignore

        is_abstract = getattr(attributes.get('Meta', {}), 'abstract', False)

        if is_abstract:
            return cls

        namespace = getattr(attributes.get('Meta', {}), 'namespace', cls_name)

        for key, value in cls.__dict__.items():  # type: str, Any
            if isinstance(value, Scene):
                scene = value

                if not scene.name:
                    scene.name = key

                if not scene.namespace:
                    scene.namespace = namespace

                cls._scenes[scene.full_name] = scene
            elif isinstance(value, Router):
                router = value

                router.namespace = namespace
                cls._routers.add(router)

        cls._init_dialogs[cls_name] = cls

        return cls


class BaseScenesStorage(ABC):
    @abstractmethod
    async def get_scenes_history(self, *,
                                 chat_id: Union[int, str],
                                 user_id: Union[int, str]) -> List[str]:
        """
        :returns: List of full names
        """

    @abstractmethod
    async def update_scenes_history(self, *,
                                    chat_id: Union[int, str],
                                    user_id: Union[int, str],
                                    new_scenes_history: Sequence[str]) -> Sequence[str]:
        """
        :returns: Scenes History
        """

    @abstractmethod
    async def set_current_scene(self, *,
                                chat_id: Union[int, str],
                                user_id: Union[int, str],
                                new_scene: 'Scene') -> List[str]:
        """
        Sets the user's current scene: append the new scene full name to scenes history.

        :returns: Scenes History
        """

    async def get_current_scene(self, *,
                                chat_id: Union[int, str],
                                user_id: Union[int, str]) -> Optional['Scene']:
        scene_ids = await self.get_scenes_history(user_id=user_id, chat_id=chat_id)

        if scene_ids:
            return Dialog._scenes.get(scene_ids[-1], None)  # NOQA
        else:
            return None

    async def get_previous_scene(self, *,
                                 chat_id: Union[int, str],
                                 user_id: Union[int, str]) -> Optional['Scene']:
        scenes_history = await self.get_scenes_history(chat_id=chat_id, user_id=user_id)

        try:
            return Dialog._scenes[scenes_history[-2]]  # NOQA
        except IndexError:
            return None

    @staticmethod
    async def get_next_scene(*,
                             current_scene: Optional['Scene'],
                             current_event_type: str,
                             handler_args: tuple,
                             handler_kwargs: dict) -> Optional['Scene']:
        if current_scene:
            for relation in current_scene.relations:
                if current_event_type in relation.event_types and \
                        await relation.check_filters(*handler_args,
                                                     event_type=current_event_type,
                                                     **handler_kwargs):
                    for on_transition_function in relation.on_transition:
                        await run_function(on_transition_function, *handler_args, **handler_kwargs)

                    return await relation.get_scene(*handler_args, **handler_kwargs)

        for router in Dialog._routers:  # NOQA
            for relation in router.relations:
                if current_event_type in relation.event_types and \
                        await relation.check_filters(*handler_args,
                                                     event_type=current_event_type,
                                                     **handler_kwargs):
                    for on_transition_function in relation.on_transition:
                        await run_function(on_transition_function, *handler_args, **handler_kwargs)

                    return await relation.get_scene(*handler_args, **handler_kwargs)

        return None


class FutureDialog:
    """
    Used to create a link to a dialog that has not yet been initialized.
    Can only be used to create scene relation.
    """
    def __init__(self, class_name: Optional[str] = None):
        self.class_name = class_name

    def __getattr__(self, scene_name: str) -> FutureScene:
        return FutureScene(class_name=self.class_name, scene_name=scene_name)


class Handler:
    def __init__(self, type_: str):
        self._type = type_

    async def __call__(self, *args, **kwargs):
        """
        Является функций-маршрутизатором.
        Перенаправляет полученный апдейт в нужную сцену.
        """

        obj: Union[AiogramMessage, CallbackQuery, TelegramObject] = args[0]

        try:
            chat_id = obj.chat.id
        except AttributeError:
            chat_id = obj.message.chat.id

        user_id = obj.from_user.id

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
                current_scene=current_scene,
                current_event_type=self._type,
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
                    chat_id=chat_id,
                    user_id=obj.from_user.id,
                    new_scene=next_scene)

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


class View:
    @staticmethod
    async def send_new_message(*args, **kwargs) -> List[AiogramMessage]:
        obj: Union[AiogramMessage, CallbackQuery, TelegramObject] = args[0]

        sent_messages = []

        try:
            chat_id = obj.chat.id
        except AttributeError:
            chat_id = obj.message.chat.id

        scene: 'Scene' = kwargs.get(Dialog.KEYS_FOR_CURRENT_SCENES[0])

        async for message_to_send in scene.get_messages(*args, **kwargs):
            sent_message = await message_to_send.send(chat_id=chat_id, bot=obj.bot)
            sent_messages.append(sent_message)

        if isinstance(obj, CallbackQuery):
            await obj.answer()

        return sent_messages


class ScenesStorage(BaseScenesStorage):
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


class Scene:
    def __init__(self,
                 *,
                 name: Optional[str] = None,
                 namespace: Optional[str] = None,

                 messages: Union[
                     'BaseMessage', Sequence['BaseMessage'],

                     Callable[..., 'BaseMessage'],
                     Callable[..., Sequence['BaseMessage']],
                     Callable[..., Awaitable['BaseMessage']],
                     Callable[..., Sequence[Awaitable['BaseMessage']]],

                     Sequence[Callable[..., 'BaseMessage']],
                     Sequence[Callable[..., Sequence['BaseMessage']]],
                     Sequence[Callable[..., Awaitable['BaseMessage']]],
                     Sequence[Callable[..., Sequence[Awaitable['BaseMessage']]]]
                 ] = tuple(),

                 relations: Union['Relation', Sequence['Relation']] = tuple(),

                 view_function: Callable = View.send_new_message,
                 on_pre_view: Union[Callable, Sequence[Callable]] = tuple(),
                 on_post_view: Union[Callable, Sequence[Callable]] = tuple(),

                 on_enter: Union[Callable, Sequence[Callable]] = tuple(),
                 on_exit: Union[Callable, Sequence[Callable]] = tuple(),

                 is_transitional_scene: bool = False,
                 can_stay: bool = True,
                 custom_kwargs: Optional[dict] = None,
                 ):
        self.name: str = name  # Will be updated by `DialogMeta`
        self.namespace: str = namespace  # Will be updated by `DialogMeta`

        if isinstance(messages, BaseMessage) or isinstance(messages, Callable):
            messages = (messages,)
        if isinstance(relations, Relation):
            relations = (relations,)
        if isinstance(on_pre_view, Callable):
            on_pre_view = (on_pre_view,)
        if isinstance(on_post_view, Callable):
            on_post_view = (on_post_view,)
        if isinstance(on_enter, Callable):
            on_enter = (on_enter,)
        if isinstance(on_exit, Callable):
            on_exit = (on_exit,)

        self.messages = messages
        self.relations = relations

        _view_function = deepcopy(view_function)

        view_function = self._pre_view(view_function)
        view_function = self._post_view(view_function)
        self.view = view_function
        self.view.__wrapped__ = _view_function

        self.on_pre_view = on_pre_view
        self.on_post_view = on_post_view

        self.on_enter = on_enter
        self.on_exit = on_exit

        self.is_transitional_scene = is_transitional_scene
        self.can_stay = can_stay

        for name, value in (custom_kwargs or dict()).items():
            setattr(self, name, value)

    @property
    def full_name(self) -> str:
        """
        Returns `Scene` name with `namespace`
        :return: {self.namespace}.{self.name}
        """
        return f'{self.namespace}.{self.name}'

    def init(self, dp: Optional[Dispatcher] = None) -> None:
        if not self.name:
            raise ValueError(f"Can't initialize scene without name")

        if not self.namespace:
            raise ValueError(f"Can't initialize scene without namespace")

        Dialog._scenes[self.full_name] = self  # NOQA

        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.init_filters(dp=dp)

    async def get_messages(self, *args, **kwargs) -> AsyncIterator['BaseMessage']:
        for message in self.messages:
            if isinstance(message, BaseMessage):
                yield message
            else:
                messages: Union['BaseMessage', Sequence['BaseMessage']] = \
                    await run_function(message, *args, **kwargs)
                if isinstance(messages, BaseMessage):
                    yield messages
                else:
                    for _message in messages:
                        yield _message

    def _pre_view(self, view: Callable):
        async def wrapper(*args, **kwargs):
            for pre_handle_function in self.on_pre_view:
                await run_function(pre_handle_function, *args, **kwargs)

            return await view(*args, **kwargs)

        return wrapper

    def _post_view(self, view: Callable):
        async def wrapper(*args, **kwargs):
            view_result = await view(*args, **kwargs)
            kwargs['view_result'] = view_result

            for post_handle_function in self.on_post_view:
                await run_function(post_handle_function, *args, **kwargs)

            return view_result

        return wrapper

    def __repr__(self) -> str:
        return f'<Scene {self.full_name}>'


class Relation:
    def __init__(self,
                 to: Union[Scene, str, FutureScene,
                           Callable[..., 'Scene'],
                           Callable[..., Awaitable['Scene']]],
                 *filters_as_args: Union[Callable[..., Union[bool, Awaitable[bool]]], AbstractFilter],
                 event_types: Union[str, Sequence[str]] = (EventType.MESSAGE,),
                 on_transition: Union[Callable, Sequence[Callable]] = tuple(),
                 **filters_as_kwargs: Any
                 ):

        if isinstance(to, Scene):
            self.to_scene = to
            self.to_scene_name = to.full_name
            self.get_scene_func = None
            self.future_scene = None
        elif isinstance(to, FutureScene):
            self.to_scene = None  # type: ignore
            self.to_scene_name = None  # type: ignore
            self.get_scene_func = None
            self.future_scene = to
        elif isinstance(to, str):
            self.to_scene = None  # type: ignore
            self.to_scene_name = to
            self.get_scene_func = None  # type: ignore
            self.future_scene = None  # type: ignore
        elif isinstance(to, Callable):
            self.to_scene = None  # type: ignore
            self.to_scene_name = None  # type: ignore
            self.get_scene_func = to
            self.future_scene = None  # type: ignore

        if isinstance(event_types, str):
            event_types = (event_types,)

        self.event_types = event_types

        if isinstance(on_transition, Callable):
            on_transition = (on_transition,)

        self.on_transition = on_transition

        self.filters: Dict[str, List[Callable[..., Union[bool, Awaitable[bool]]]]] = dict()

        self._filters_as_args = filters_as_args
        self._filters_as_kwargs = filters_as_kwargs

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

    def init_scene(self, namespace: str):
        if self.to_scene_name:
            if self.to_scene_name.count('.') == 0:
                self.to_scene_name = f"{namespace}.{self.to_scene_name}"
            try:
                self.to_scene = Dialog._scenes[self.to_scene_name]  # NOQA
            except KeyError:
                raise RuntimeError(f'Scene "{self.to_scene_name}" not found')
        elif self.to_scene:
            self.to_scene_name = self.to_scene.full_name
        elif self.future_scene:
            if self.future_scene.class_name is None:
                if self.future_scene.scene_name.count('.') == 0:
                    self.to_scene_name = f"{namespace}.{self.future_scene.scene_name}"
                else:
                    self.to_scene_name = self.future_scene.scene_name

                try:
                    self.to_scene = Dialog._scenes[self.to_scene_name]  # NOQA
                except KeyError:
                    raise RuntimeError(f'Scene "{self.to_scene_name}" not found')

                return

            cls = Dialog._init_dialogs.get(self.future_scene.class_name)  # NOQA

            if cls is None:
                raise RuntimeError(f'Class "{self.future_scene.class_name}" for "FutureScene" not found!')

            scene: 'Scene' = getattr(cls, self.future_scene.scene_name)

            if scene is None:
                raise RuntimeError(f'Scene name "{self.future_scene.scene_name}" for "FutureScene" not found!')

            self.to_scene = scene
            self.to_scene_name = scene.full_name

    async def get_scene(self, *args, **kwargs) -> 'Scene':
        if self.get_scene_func:
            return await run_function(self.get_scene_func, *args, **kwargs)
        else:
            return self.to_scene

    async def check_filters(self, *args, event_type: str, **kwargs) -> bool:
        for filter_ in self.filters[event_type]:
            if not await run_function(filter_, *args, **kwargs):
                return False
        else:
            return True


class Router:
    def __init__(self,
                 *relations: 'Relation',
                 namespace: Optional[str] = None):
        self.relations = relations
        self.namespace: str = namespace  # type: ignore

    def init(self, dp: Optional[Dispatcher] = None):
        Dialog._routers.add(self)  # NOQA

        for relation in self.relations:
            relation.init_scene(namespace=self.namespace)
            relation.init_filters(dp)


class Dialog(metaclass=_DialogMeta):
    scenes_storage: BaseScenesStorage = NotImplemented  # type: ignore

    _init_dialogs: Dict[str, 'Dialog'] = dict()  # Dict[class_name, 'Dialog']
    _scenes: Dict[str, 'Scene'] = dict()  # Dict[Scene.full_name, Scene]
    _routers: Set['Router'] = set()

    # Configuration
    KEYS_FOR_PREVIOUS_SCENES: Sequence[str] = ('previous_scene',)
    KEYS_FOR_CURRENT_SCENES: Sequence[str] = ('current_scene',)
    KEYS_FOR_NEXT_SCENES: Sequence[str] = ('next_scene',)

    @classmethod
    def init(cls, dp: Optional[Dispatcher] = None):
        for scene in cls._scenes.values():
            scene.init(dp=dp)

        for router in cls._routers:
            router.init(dp=dp)

    @classmethod
    def register(cls,
                 dp: Dispatcher,
                 scenes_storage: Optional[BaseScenesStorage] = None):
        cls.scenes_storage = scenes_storage or ScenesStorage(aiogram_storage=dp.storage)
        cls.init(dp)

        dp.register_message_handler(Handler(type_=EventType.MESSAGE))
        dp.register_callback_query_handler(Handler(type_=EventType.CALLBACK_QUERY))
        dp.register_poll_handler(Handler(type_=EventType.POLL))
        dp.register_poll_answer_handler(Handler(type_=EventType.POLL_ANSWER))
        dp.register_channel_post_handler(Handler(type_=EventType.CHANNEL_POST))
        dp.register_chat_member_handler(Handler(type_=EventType.CHAT_MEMBER))
        dp.register_chosen_inline_handler(Handler(type_=EventType.CHOSEN_INLINE_RESULT))
        dp.register_edited_message_handler(Handler(type_=EventType.EDITED_MESSAGE))
        dp.register_pre_checkout_query_handler(Handler(type_=EventType.PRE_CHECKOUT_QUERY))
        dp.register_shipping_query_handler(Handler(type_=EventType.SHIPPING_QUERY))
        dp.register_my_chat_member_handler(Handler(type_=EventType.MY_CHAT_MEMBER))

        # TODO: register all Events

    class Meta:
        """
        The ``Meta`` class is used to configure metadata for the Dialog.
        """
        abstract: bool = False
        namespace: str = ''
