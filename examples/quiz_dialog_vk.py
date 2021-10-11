import logging
import os
from typing import Optional

from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from vkbottle import Bot, Keyboard, KeyboardButtonColor, Text
from vkbottle.bot import Message as VKMessage

from dialog.shared.storage import AiogramBasedScenesStorage
from dialog.vk import Dialog, Relation, Router, Scene
from dialog.vk.middlewares import FSMMiddleware
from dialog.vk.types import Message

logging.basicConfig(level=logging.INFO)


def is_game_started(*, current_scene: Optional['Scene']) -> bool:
    return bool(current_scene)


def is_game_not_started(*, current_scene: Optional['Scene']) -> bool:
    return not is_game_started(current_scene=current_scene)


async def process_correct_answer(message: VKMessage, state: FSMContext):
    async with state.proxy() as data:
        data['points'] = data.get('points', 0) + 3

    await message.answer('Верно! ✅', reply_to=message.id)


async def process_incorrect_answer(message: VKMessage, state: FSMContext):
    async with state.proxy() as data:
        data['points'] = data.get('points', 0) - 3

    await message.answer('Неверно! ❌', reply_to=message.id)


async def process_move_to_previous_scene(message: VKMessage):
    current_scenes_history = await Dialog.scenes_storage.get_scenes_history(
        chat_id=message.chat_id, user_id=message.from_id
    )

    await Dialog.scenes_storage.update_scenes_history(
        chat_id=message.chat_id,
        user_id=message.from_id,
        new_scenes_history=current_scenes_history[:-1],
    )


async def get_end_game_message(*, state: FSMContext) -> Message:
    data = await state.get_data()

    return Message(message='Спасибо за игру!\n'
                           f'Ваш результат: {data.get("points", 0)} очков!')


async def get_score_message(*, state: FSMContext) -> Message:
    data = await state.get_data()

    return Message(message=f"Ваши очки: {data.get('points', 0)}")


def create_keyboard() -> str:
    kb = (
        Keyboard()
        .row().add(
            action=Text('Перезапустить игру', {'action': 'restart'}),
            color=KeyboardButtonColor.POSITIVE,
        )
        .row().add(
            action=Text('Повторить вопрос', {'action': 'repeat'}),
            color=KeyboardButtonColor.POSITIVE,
        )
        .row().add(
            action=Text('Посмотреть количество очков', {'action': 'score'}),
            color=KeyboardButtonColor.POSITIVE,
        )
    )

    return kb.get_json()


class QuizUtils(Dialog):
    router = Router(
        Relation(
            lambda *, current_scene: current_scene or QuizUtils.start_scene,  # type: ignore
            is_game_not_started,
        ),
        Relation(
            lambda *, current_scene: current_scene or QuizUtils.start_scene,  # type: ignore
            payload={'action': 'restart'},
        ),
        Relation(
            'QuizUtils.score',
            is_game_started,
            payload={'action': 'score'}
        ),
        Relation(
            lambda *, current_scene: current_scene,
            is_game_started,
            payload={'action': 'repeat'},
        ),
        Relation(
            lambda *, previous_scene: previous_scene,
            is_game_started,
            text='back',
            on_transition=process_move_to_previous_scene,
        ),
        Relation(
            'QuizUtils.incorrect_answer',
            is_game_started
        ),
        Relation(
            'QuizUtils.game_is_not_started_scene',
            is_game_not_started
        ),
    )

    game_is_not_started_scene = Scene(
        messages=Message(message='Вы не начали игру!\n'
                                 'Напишите /start, чтобы начать игру!'),
        can_stay=False,
    )

    start_scene = Scene(
        messages=lambda msg: Message(message='Приветствуем в игре!',
                                     keyboard=create_keyboard()),
        relations=Relation('Questions.q1', lambda: True),
        is_transitional_scene=True,
    )

    end_scene = Scene(
        messages=get_end_game_message,
        relations=Relation('QuizUtils.end_scene', lambda: True),
    )

    score = Scene(messages=get_score_message, can_stay=False)
    incorrect_answer = Scene(on_enter=process_incorrect_answer, can_stay=False)


class Questions(Dialog):
    q1 = Scene(
        messages=Message(message='Вопрос 1:\n2 + 2 = ?'),
        relations=Relation('Questions.q2', text=['4', 'Четыре'],
                           on_transition=process_correct_answer),
    )

    q2 = Scene(
        messages=Message(message='Вопрос 2:\n3 + 3 = ?'),
        relations=Relation(
            'Questions.q3',
            text=['6', 'Шесть', 'Six'],
            on_transition=process_correct_answer,
        ),
    )

    q3 = Scene(
        messages=Message(message='Вопрос 3:\n6 + 3 = ?'),
        relations=Relation(
            QuizUtils.end_scene,
            text=['9', 'Девять', 'Nine'],
            on_transition=process_correct_answer,
        ),
    )

    class Meta:
        namespace = 'Questions'


def run_bot():
    bot = Bot(token=os.getenv('VK_TOKEN'))

    storage = MemoryStorage()

    bot.labeler.message_view.register_middleware(
        FSMMiddleware(storage=storage)
    )

    Dialog.register_handlers(
        bot=bot,
        scenes_storage=AiogramBasedScenesStorage(storage=storage)
    )

    bot.run_forever()


if __name__ == '__main__':
    run_bot()
