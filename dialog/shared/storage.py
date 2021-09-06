from typing import List, Sequence, Union

from aiogram.dispatcher.storage import BaseStorage

from dialog.bases import BaseScene, BaseScenesStorage


class AiogramBasedScenesStorage(BaseScenesStorage):
    def __init__(self, storage: BaseStorage, data_key: str = 'scenes_history'):
        self.storage = storage
        self.data_key = data_key

    async def get_scenes_history(self, *,
                                 chat_id: Union[int, str],
                                 user_id: Union[int, str]) -> List[str]:
        data = await self.storage.get_data(chat=chat_id, user=user_id)

        await self.storage.update_data(chat=chat_id, user=user_id)

        return data.get(self.data_key, [])

    async def update_scenes_history(self, *,
                                    chat_id: Union[int, str],
                                    user_id: Union[int, str],
                                    new_scenes_history: Sequence[str]) -> Sequence[str]:
        await self.storage.update_data(chat=chat_id, user=user_id, **{self.data_key: new_scenes_history})

        return new_scenes_history

    async def set_current_scene(self, *,
                                chat_id: Union[int, str],
                                user_id: Union[int, str],
                                new_scene: 'BaseScene') -> List[str]:
        data = await self.storage.get_data(chat=chat_id, user=user_id)

        scenes_history: List[str] = data.get(self.data_key, [])
        try:
            if scenes_history[-1] != new_scene.full_name:
                scenes_history.append(new_scene.full_name)
        except IndexError:
            scenes_history.append(new_scene.full_name)

        await self.storage.update_data(chat=chat_id, user=user_id, **{self.data_key: scenes_history})

        return scenes_history
