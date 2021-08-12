import asyncio
import logging
from typing import Optional, Type

from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import BotCommand
from aiogram.types import Message as AiogramMessage
from aiogram.types import ReplyKeyboardRemove

from dialog.defaults import FutureDialog
from dialog.telegram import Dialog, Relation, Router, Scene
from dialog.telegram.types import Message


logging.basicConfig(level=logging.INFO)


def is_game_started(*, current_scene: Optional['Scene']) -> bool:
    return bool(current_scene)


def is_game_not_started(*, current_scene: Optional['Scene']) -> bool:
    return not is_game_started(current_scene=current_scene)


async def process_correct_answer(message: AiogramMessage, state: FSMContext):
    async with state.proxy() as data:
        data['points'] = data.get('points', 0) + 3

    if message.from_user.language_code == 'ru':
        await message.reply(f'<b>Верно! ✅</b>')
    else:
        await message.reply(f'<b>Correct! ✅</b>')


async def process_incorrect_answer(message: AiogramMessage, state: FSMContext):
    async with state.proxy() as data:
        data['points'] = data.get('points', 0) - 3

    if message.from_user.language_code == 'ru':
        await message.reply(f'<b>Неверно! ❌</b>')
    else:
        await message.reply(f'<b>Incorrect! ❌</b>')


async def process_move_to_previous_scene(message: AiogramMessage):
    current_scenes_history = await Dialog.scenes_storage.get_scenes_history(chat_id=message.chat.id,
                                                                            user_id=message.from_user.id)

    await Dialog.scenes_storage.update_scenes_history(chat_id=message.chat.id,
                                                      user_id=message.from_user.id,
                                                      new_scenes_history=current_scenes_history[:-1])


async def get_end_game_message(message: AiogramMessage, state: FSMContext) -> Message:
    data = await state.get_data()

    if message.from_user.language_code == 'ru':
        return Message(text='Спасибо за игру!\n'
                            f'Ваш результат: <b>{data.get("points", 0)}</b> очков!')
    else:
        return Message(text='Thank you for playing!\n'
                            f'Your score: <b>{data.get("points", 0)}</b> points!')


async def get_score_message(message: AiogramMessage, state: FSMContext) -> Message:
    data = await state.get_data()

    if message.from_user.language_code == 'ru':
        return Message(text=f"Ваши очки: {data.get('points', 0)}")
    else:
        return Message(text=f"Your score: {data.get('points', 0)}")


class QuizUtils(Dialog):
    QuizUtils: Type['QuizUtils'] = FutureDialog('QuizUtils')
    Questions: Type['Questions'] = FutureDialog('Questions')

    router = Router(
        Relation(lambda *, current_scene: current_scene or QuizUtils.start_scene,
                 commands='start'),
        Relation(QuizUtils.score,
                 is_game_started, commands='score'),
        Relation(lambda *, current_scene: current_scene,
                 is_game_started, commands='repeat'),
        Relation(lambda *, previous_scene: previous_scene,
                 is_game_started, commands='back', on_transition=process_move_to_previous_scene),
        Relation(QuizUtils.incorrect_answer, is_game_started),
        Relation(QuizUtils.game_is_not_started_scene, is_game_not_started)
    )

    game_is_not_started_scene = Scene(
        messages=lambda msg:
            Message(text="Вы не начали игру!\nНапишите /start, чтобы начать игру!") if msg.from_user.language_code == 'ru' else  # NOQA
            Message(text="You haven't started the game!\nType /start to start the game!"),
        can_stay=False)

    start_scene = Scene(
        messages=lambda msg:
            Message(text=f'Приветствуем в игре, <b>{msg.from_user.first_name}</b>!',
                    keyboard=ReplyKeyboardRemove()) if msg.from_user.language_code == 'ru' else
            Message(text=f'Welcome to the game, <b>{msg.from_user.first_name}</b>!',
                    keyboard=ReplyKeyboardRemove()),
        relations=Relation(Questions.q1, lambda: True),
        is_transitional_scene=True)

    end_scene = Scene(messages=get_end_game_message,
                      relations=Relation(QuizUtils.end_scene, lambda: True))

    score = Scene(messages=get_score_message, can_stay=False)
    incorrect_answer = Scene(on_enter=process_incorrect_answer, can_stay=False)


class Questions(Dialog):
    Questions: Type['Questions'] = FutureDialog('Questions')

    q1 = Scene(
        messages=lambda msg:
            Message(text='<i>Вопрос 1:\n</i>2 + 2 = ?') if msg.from_user.language_code == 'ru' else
            Message(text='<i>Question 1:\n</i>2 + 2 = ?'),
        relations=Relation(Questions.q2, text=('4', 'Четыре', 'Four'),
                           on_transition=process_correct_answer))

    q2 = Scene(
        messages=lambda msg:
            Message(text='<i>Вопрос 2:\n</i>3 + 3 = ?') if msg.from_user.language_code == 'ru' else
            Message(text='<i>Question 2:\n</i>3 + 3 = ?'),
        relations=Relation(Questions.q3, text=('6', 'Шесть', 'Six'),
                           on_transition=process_correct_answer))

    q3 = Scene(
        messages=lambda msg:
            Message(text='<i>Вопрос 3:\n</i>6 + 3 = ?') if msg.from_user.language_code == 'ru' else
            Message(text='<i>Question 3:\n</i>6 + 3 = ?'),
        relations=Relation(QuizUtils.end_scene, text=('9', 'Девять', 'Nine'),
                           on_transition=process_correct_answer))

    class Meta:
        namespace = 'Questions'


async def run_bot():
    bot = Bot(token='TOKEN', parse_mode='html')  # NOQA
    dp = Dispatcher(bot, storage=MemoryStorage())

    await bot.set_my_commands(
        commands=[BotCommand('start', 'Перезапуск бота'),
                  BotCommand('repeat', 'Повторить вопрос'),
                  BotCommand('score', 'Посмотреть количество очков')],
        language_code='ru')

    await bot.set_my_commands(
        commands=[BotCommand('start', 'Restart the bot'),
                  BotCommand('repeat', 'Repeat the question'),
                  BotCommand('score', 'Check the score')],
        language_code=None)

    Dialog.register(dp)

    await dp.start_polling()


if __name__ == '__main__':
    asyncio.run(run_bot())
