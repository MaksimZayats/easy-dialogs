from abc import ABC, ABCMeta, abstractmethod
from copy import deepcopy
from typing import (Any, AsyncIterator, Awaitable, Callable, Dict, Iterable, List, Optional, Sequence, Set,
                    Tuple, Type, Union)

from dialog.shared.types import FutureScene
from dialog.shared.utils import run_function


class _DialogMeta(ABCMeta):
    def __new__(mcs, cls_name: str, superclasses: tuple, attributes: dict, **kwargs):
        cls: Type['BaseDialog'] = super().__new__(mcs, cls_name, superclasses, attributes)  # type: ignore

        is_abstract = getattr(attributes.get('Meta', {}), 'abstract', False)

        if is_abstract:
            return cls

        namespace = getattr(attributes.get('Meta', {}), 'namespace', cls_name)

        for key, value in cls.__dict__.items():  # type: str, Any
            if isinstance(value, BaseScene):
                scene = value

                if not scene.name:
                    scene.name = key

                if not scene.namespace:
                    scene.namespace = namespace

                scene.register()
            elif isinstance(value, BaseRouter):
                router = value

                if not router.namespace:
                    router.namespace = namespace

                router.register()

        cls.register_dialog(dialog=cls)

        return cls

    @property
    def initialized_scenes(cls: Type['BaseDialog']) -> Dict[str, 'BaseScene']:  # type: ignore
        return cls._initialized_scenes

    @property
    def initialized_routers(cls: Type['BaseDialog']) -> Set['BaseRouter']:  # type: ignore
        return cls._initialized_routers

    @property
    def initialized_dialogs(cls: Type['BaseDialog']) -> Dict[str, Type['BaseDialog']]:  # type: ignore
        return cls._initialized_dialogs


class BaseFiltersGroup(ABC):
    def __init__(self,
                 *filters_as_args: Union[
                     Callable[..., bool],
                     Callable[..., Awaitable[bool]],
                     Callable[..., dict],
                     Callable[..., Awaitable[dict]],
                     object,
                 ],
                 event_types: Optional[Union[str, Sequence[str]]] = None,
                 **filters_as_kwargs: Any):
        self.filters_as_args = filters_as_args
        self.filters_as_kwargs = filters_as_kwargs

        if isinstance(event_types, str):
            event_types = (event_types,)

        self.event_types = event_types or self.default_event_types

        self.filters_to_check: Dict[str, List[Callable]] = {}  # Dict[`EventType(str)`, List[Callable]]]

    @property
    @abstractmethod
    def default_event_types(self) -> Tuple[str]:
        pass

    @abstractmethod
    def init(self, *args, **kwargs):
        pass

    async def check(self, handler_args: tuple, handler_kwargs: Dict[str, Any], event_type: str) -> bool:
        for filter_ in self.filters_to_check[event_type]:
            result = await run_function(filter_, *handler_args, **handler_kwargs)

            if isinstance(result, dict):
                handler_kwargs.update(result)
            else:
                if not result:
                    return False
        else:
            return True


class BaseMessage(ABC):
    @abstractmethod
    async def send(self, *args, **kwargs):
        pass


class BaseScene(ABC):
    def __init__(self, *,
                 name: Optional[str] = None,
                 namespace: Optional[str] = None,
                 messages: Union[
                     BaseMessage,
                     Sequence[BaseMessage],
                     Callable[..., BaseMessage],
                     Callable[..., Sequence[BaseMessage]],
                     Callable[..., Awaitable[BaseMessage]],
                     Callable[..., Sequence[Awaitable[BaseMessage]]],
                     Sequence[Callable[..., BaseMessage]],
                     Sequence[Callable[..., Sequence[BaseMessage]]],
                     Sequence[Callable[..., Awaitable[BaseMessage]]],
                     Sequence[Callable[..., Sequence[Awaitable[BaseMessage]]]],
                 ] = (),
                 relations: Union['BaseRelation', Sequence['BaseRelation']] = (),
                 view_function: Optional[Callable] = None,
                 on_pre_view: Union[Callable, Sequence[Callable]] = (),
                 on_post_view: Union[Callable, Sequence[Callable]] = (),
                 on_enter: Union[Callable, Sequence[Callable]] = (),
                 on_exit: Union[Callable, Sequence[Callable]] = (),
                 filters: Optional[BaseFiltersGroup] = None,
                 is_transitional_scene: bool = False,
                 can_stay: bool = True,
                 **custom_kwargs: Any):
        """
        :param name: Name of the `Scene`. If `None` will be updated by `DialogMeta`.
        :param namespace: Namespace of the `Scene`. If `None` will be updated by `DialogMeta`.
        :param messages: Will be used in the `view' function.
        :param relations: Relations of the `Scene`.
        :param view_function: If `None` the default view function will be used.
        :param on_pre_view: Functions that will be executed before the main view function.
        :param on_post_view: Functions that will be executed after the main view function.
                             To get the result of executing the main view function,
                             specify `view_result` in the function keyword parameters.
        :param on_enter: Functions that will be executed when switching to this scene.
        :param on_exit: Functions that will be executed when exiting this scene.
        :param filters: Filters of the `Scene`. If `None` will be ignored.
        :param is_transitional_scene: If `True`, then immediately after switching to this scene,
                                      relations will be checked.
        :param can_stay: If `False`, then this scene cannot be set as the current scene.
        :param custom_kwargs:
        """
        self.name = name  # Will be updated by `DialogMeta`
        self.namespace = namespace  # Will be updated by `DialogMeta`

        if not isinstance(messages, Iterable):
            messages = (messages,)
        if not isinstance(relations, Iterable):
            relations = (relations,)
        if not isinstance(on_pre_view, Iterable):
            on_pre_view = (on_pre_view,)
        if not isinstance(on_post_view, Iterable):
            on_post_view = (on_post_view,)
        if not isinstance(on_enter, Iterable):
            on_enter = (on_enter,)
        if not isinstance(on_exit, Iterable):
            on_exit = (on_exit,)

        self.messages = messages
        self.relations = relations

        view_function = view_function or self.default_view
        _view_function = deepcopy(view_function)

        view_function = self._pre_view(view_function)
        view_function = self._post_view(view_function)
        self.view = view_function
        self.view.__wrapped__ = _view_function

        self.on_pre_view = on_pre_view
        self.on_post_view = on_post_view

        self.on_enter = on_enter
        self.on_exit = on_exit

        self.filters = filters

        self.is_transitional_scene = is_transitional_scene
        self.can_stay = can_stay

        for name, value in custom_kwargs.items():
            setattr(self, name, value)

    @abstractmethod
    def init(self, *args, **kwargs):
        pass

    @property
    @abstractmethod
    def default_view(self) -> Callable:
        pass

    async def get_messages(self, *args, **kwargs) -> AsyncIterator[BaseMessage]:
        for message in self.messages:
            if isinstance(message, BaseMessage):
                yield message
            elif isinstance(message, Callable):
                messages: Union[BaseMessage, Sequence[BaseMessage]] = \
                    await run_function(message, *args, **kwargs)

                if isinstance(messages, BaseMessage):
                    yield messages
                else:
                    for message_ in messages:
                        yield message_

    @property
    def full_name(self) -> str:
        """
        Returns `Scene` name with `namespace`
        :return: {self.namespace}.{self.name}
        """
        return f'{self.namespace}.{self.name}'

    def register(self) -> None:
        if not self.name:
            raise ValueError("Can't register `Scene` without name")

        if not self.namespace:
            raise ValueError("Can't register `Scene` without namespace")

        BaseDialog.register_scene(scene=self)

    def _pre_view(self, view: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            for pre_handle_function in self.on_pre_view:
                await run_function(pre_handle_function, *args, **kwargs)

            return await view(*args, **kwargs)

        return wrapper

    def _post_view(self, view: Callable) -> Callable:
        async def wrapper(*args, **kwargs):
            view_result = await view(*args, **kwargs)
            kwargs['view_result'] = view_result

            for post_handle_function in self.on_post_view:
                await run_function(post_handle_function, *args, **kwargs)

            return view_result

        return wrapper

    def __repr__(self) -> str:
        return f'<Scene {self.full_name}>'


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
                                    new_scenes_history: Sequence[str]) -> List[str]:
        """
        :returns: Scenes History
        """

    @abstractmethod
    async def set_current_scene(self, *,
                                chat_id: Union[int, str],
                                user_id: Union[int, str],
                                new_scene: 'BaseScene') -> List[str]:
        """
        Sets the user's current scene: append the new scene full name to scenes history.

        :returns: Scenes History
        """

    async def get_current_scene(self, *,
                                chat_id: Union[int, str],
                                user_id: Union[int, str]) -> Optional['BaseScene']:
        scene_ids = await self.get_scenes_history(user_id=user_id, chat_id=chat_id)

        if scene_ids:
            return BaseDialog.initialized_scenes.get(scene_ids[-1], None)
        else:
            return None

    async def get_previous_scene(self, *,
                                 chat_id: Union[int, str],
                                 user_id: Union[int, str]) -> Optional['BaseScene']:
        scenes_history = await self.get_scenes_history(chat_id=chat_id, user_id=user_id)

        try:
            return BaseDialog.initialized_scenes[scenes_history[-2]]
        except IndexError:
            return None

    @staticmethod
    async def get_next_scene(*,
                             current_scene: Optional['BaseScene'],
                             current_event_type: str,
                             handler_args: tuple,
                             handler_kwargs: dict) -> Optional['BaseScene']:
        if current_scene:
            for relation in current_scene.relations:  # NOQA
                if current_event_type in relation.filters.event_types and \
                        await relation.filters.check(handler_args=handler_args,
                                                     handler_kwargs=handler_kwargs,
                                                     event_type=current_event_type):
                    next_scene = await relation.get_scene(*handler_args, **handler_kwargs)

                    if next_scene.filters:
                        if not await next_scene.filters.check(handler_args=handler_args,
                                                              handler_kwargs=handler_kwargs,
                                                              event_type=current_event_type):
                            continue

                    for on_transition_function in relation.on_transition:
                        await run_function(
                            on_transition_function,
                            *handler_args,
                            **handler_kwargs | {BaseDialog.KEY_FOR_NEXT_SCENES: next_scene}
                        )

                    return next_scene

        for router in BaseDialog.initialized_routers:
            for relation in router.relations:  # NOQA
                if current_event_type in relation.filters.event_types and \
                    await relation.filters.check(handler_args=handler_args,
                                                 handler_kwargs=handler_kwargs,
                                                 event_type=current_event_type):
                    next_scene = await relation.get_scene(*handler_args, **handler_kwargs)

                    if next_scene.filters:
                        if not await next_scene.filters.check(handler_args=handler_args,
                                                              handler_kwargs=handler_kwargs,
                                                              event_type=current_event_type):
                            continue

                    for on_transition_function in relation.on_transition:
                        await run_function(
                            on_transition_function,
                            *handler_args,
                            **handler_kwargs | {BaseDialog.KEY_FOR_NEXT_SCENES: next_scene}
                        )

                    return next_scene

        return None


class BaseRelation(ABC):
    def __init__(self,
                 to: Union[
                     BaseScene,
                     str,
                     FutureScene,
                     Callable[..., 'BaseScene'],
                     Callable[..., Awaitable['BaseScene']],
                 ],
                 *filters_as_args: Union[
                     Callable[..., bool],
                     Callable[..., Awaitable[bool]],
                     Callable[..., dict],
                     Callable[..., Awaitable[dict]],
                     object,
                 ],
                 event_types: Optional[Union[str, Sequence[str]]] = None,
                 on_transition: Union[Callable, Sequence[Callable]] = tuple(),
                 **filters_as_kwargs: Any):
        if isinstance(to, BaseScene):
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

        if isinstance(on_transition, Callable):
            on_transition = (on_transition,)

        self.on_transition = on_transition

        self.filters = \
            self.default_filters_group(*filters_as_args, event_types=event_types, **filters_as_kwargs)

    @property
    @abstractmethod
    def default_filters_group(self) -> Type[BaseFiltersGroup]:
        pass

    def init_scene(self, namespace: str):
        if self.to_scene_name:
            if self.to_scene_name.count('.') == 0:
                self.to_scene_name = f"{namespace}.{self.to_scene_name}"
            try:
                self.to_scene = BaseDialog.initialized_scenes[self.to_scene_name]
            except KeyError:
                raise RuntimeError(f'Scene "{self.to_scene_name}" not found')
        elif self.to_scene:
            self.to_scene_name = self.to_scene.full_name
        elif self.future_scene:
            if self.future_scene.class_name is None:
                if self.future_scene.scene_name.count('.') == 0:
                    self.to_scene_name = f'{namespace}.{self.future_scene.scene_name}'
                else:
                    self.to_scene_name = self.future_scene.scene_name

                try:
                    self.to_scene = BaseDialog.initialized_scenes[self.to_scene_name]
                except KeyError:
                    raise RuntimeError(f'Scene "{self.to_scene_name}" not found')

                return

            cls = BaseDialog.initialized_dialogs.get(self.future_scene.class_name)

            if cls is None:
                raise RuntimeError(f'Class "{self.future_scene.class_name}" for "FutureScene" not found!')

            scene: Optional['BaseScene'] = getattr(cls, self.future_scene.scene_name)

            if scene is None:
                raise RuntimeError(
                    f'Scene name "{self.future_scene.scene_name}" for "FutureScene" not found!'
                )

            self.to_scene = scene
            self.to_scene_name = scene.full_name

    async def get_scene(self, *args, **kwargs) -> 'BaseScene':
        if self.get_scene_func:
            return await run_function(self.get_scene_func, *args, **kwargs)
        else:
            return self.to_scene


class BaseRouter(ABC):
    def __init__(self, *relations: 'BaseRelation', namespace: Optional[str] = None):
        self.relations = relations
        self.namespace = namespace  # Will be updated by `DialogMeta`

    def register(self):
        if self.namespace is None:
            raise ValueError("Can't register `Router` without namespace")

        BaseDialog.register_router(router=self)

    @abstractmethod
    def init(self, *args, **kwargs):
        pass


class BaseHandler(ABC):
    def __init__(self, dialog: Type['BaseDialog'], event_type: str):
        self.Dialog = dialog
        self.event_type = event_type

        self.__name__ = f'DialogHandler: {event_type.title()}'

    @abstractmethod
    async def __call__(self, *args, **kwargs):
        pass

    @abstractmethod
    def skip_handler(self):
        pass

    async def default_handler(self,
                              handler_args: tuple,
                              handler_kwargs: Dict[str, Any],
                              chat_id: Union[str, int],
                              user_id: Union[str, int]):
        previous_scene = await self.Dialog.scenes_storage.get_previous_scene(user_id=user_id, chat_id=chat_id)
        current_scene = await self.Dialog.scenes_storage.get_current_scene(user_id=user_id, chat_id=chat_id)

        while True:  # While to skip transitional scenes
            handler_kwargs[self.Dialog.KEY_FOR_PREVIOUS_SCENES] = previous_scene
            handler_kwargs[self.Dialog.KEY_FOR_CURRENT_SCENES] = current_scene
            handler_kwargs[self.Dialog.KEY_FOR_NEXT_SCENES] = None

            next_scene = await self.Dialog.scenes_storage.get_next_scene(
                current_scene=current_scene,
                current_event_type=self.event_type,
                handler_args=handler_args,
                handler_kwargs=handler_kwargs,
            )

            if next_scene is None:
                return self.skip_handler()

            if current_scene:
                handler_kwargs[self.Dialog.KEY_FOR_NEXT_SCENES] = next_scene

                for on_exit_function in current_scene.on_exit:
                    await run_function(on_exit_function, *handler_args, **handler_kwargs)

                handler_kwargs[self.Dialog.KEY_FOR_NEXT_SCENES] = None

            if next_scene.can_stay and current_scene != next_scene:
                await self.Dialog.scenes_storage.set_current_scene(
                    chat_id=chat_id, user_id=user_id, new_scene=next_scene
                )

            handler_kwargs[self.Dialog.KEY_FOR_PREVIOUS_SCENES] = current_scene
            handler_kwargs[self.Dialog.KEY_FOR_CURRENT_SCENES] = next_scene

            for on_entry_function in next_scene.on_enter:
                await run_function(on_entry_function, *handler_args, **handler_kwargs)

            await run_function(next_scene.view, *handler_args, **handler_kwargs)

            if not next_scene.is_transitional_scene:
                break

            previous_scene, current_scene = current_scene, next_scene


class BaseDialog(ABC, metaclass=_DialogMeta):
    scenes_storage: BaseScenesStorage = NotImplemented  # type: ignore

    _initialized_dialogs: Dict[str, Type['BaseDialog']] = dict()  # Dict[class_name, Type['Dialog']]
    _initialized_scenes: Dict[str, BaseScene] = dict()  # Dict[Scene.full_name, Scene]
    _initialized_routers: Set[BaseRouter] = set()

    # Configuration
    KEY_FOR_PREVIOUS_SCENES: str = 'previous_scene'
    KEY_FOR_CURRENT_SCENES: str = 'current_scene'
    KEY_FOR_NEXT_SCENES: str = 'next_scene'

    @classmethod
    @abstractmethod
    def init(cls, *args, **kwargs):
        """
        Initializes registered scenes and routers.
        """

    @classmethod
    @abstractmethod
    def register_handlers(cls, *args, **kwargs):
        """
        Registers an event handler for the dialog
        """

    @classmethod
    def register_scene(cls, scene: BaseScene):
        cls._initialized_scenes[scene.full_name] = scene

    @classmethod
    def register_router(cls, router: BaseRouter):
        cls._initialized_routers.add(router)

    @classmethod
    def register_dialog(cls, dialog: Type['BaseDialog']):
        cls._initialized_dialogs[dialog.__name__] = dialog

    class Meta:
        """
        The ``Meta`` class is used to configure metadata for the Dialog.
        """

        abstract: bool = False
        namespace: str = ''
