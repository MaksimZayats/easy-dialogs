from dataclasses import dataclass
from typing import Optional, Union, Sequence, Callable

from aiogram import Bot
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove, \
    Message as AiogramMessage, MediaGroup, InputFile

from dialog.utils import is_url


@dataclass
class BaseMessage:
    text: Optional[str] = None

    attachment_type: Optional[str] = None
    attachments: Optional[Sequence[str]] = None

    keyboard: Optional[Union[ReplyKeyboardMarkup,
                             InlineKeyboardMarkup,
                             ReplyKeyboardRemove]] = None

    async def send(self,
                   chat_id: Union[str, int],
                   bot: Optional[Bot] = None,
                   **kwargs) -> Union[AiogramMessage, Sequence[AiogramMessage]]:
        bot = bot or Bot.get_current()

        # ? Add limiter ?

        if self.attachment_type and self.attachments:
            if len(self.attachments) > 1:
                if self.attachment_type == AttachmentType.STICKER:
                    sent_messages = []

                    if self.text:
                        sent_messages.append(await bot.send_message(chat_id, self.text, **kwargs))

                    for attachment in self.attachments[:-1]:
                        sent_messages.append(await bot.send_sticker(chat_id, attachment, **kwargs))

                    sent_messages.append(
                        await bot.send_sticker(
                            chat_id, self.attachments[-1],
                            reply_markup=self.keyboard, **kwargs))

                    return sent_messages
                elif self.attachment_type == AttachmentType.ANIMATION:
                    sent_messages = []

                    for attachment in self.attachments[:-1]:
                        sent_messages.append(
                            await bot.send_animation(chat_id, attachment, **kwargs))

                    sent_messages.append(
                        await bot.send_animation(
                            chat_id, self.attachments[-1],
                            caption=self.text, reply_markup=self.keyboard, **kwargs))

                    return sent_messages
                else:
                    """Если вложений > 1. Отправка медиа группы"""
                    media_group = MediaGroup()
                    attach_method: Callable =\
                        getattr(media_group, f'attach_{self.attachment_type.lower()}', None)

                    if attach_method is None:
                        raise ValueError(f'Cant attach "{self.attachment_type}" to media group')

                    if is_url(self.attachments[0]):
                        attach_method(InputFile.from_url(url=self.attachments[0]), self.text)
                    else:
                        attach_method(InputFile(path_or_bytesio=self.attachments[0]), self.text)

                    for attachment in self.attachments[1:]:
                        if is_url(attachment):
                            attach_method(InputFile.from_url(url=attachment))
                        else:
                            attach_method(InputFile(path_or_bytesio=attachment))

                    return await bot.send_media_group(
                        chat_id=chat_id, media=media_group, **kwargs)
            else:
                send_method: Callable = \
                    getattr(bot, f'send_{self.attachment_type.lower()}', None)

                if send_method is None:
                    raise ValueError(f'{self.attachment_type} is unavailable media type')

                if self.attachment_type == AttachmentType.STICKER:
                    if self.text:
                        return (
                            await bot.send_message(chat_id, self.text, **kwargs),
                            await send_method(
                                chat_id, self.attachments[0],
                                reply_markup=self.keyboard, **kwargs)
                        )
                    else:
                        return await send_method(
                            chat_id, self.attachments[0],
                            reply_markup=self.keyboard, **kwargs)
                else:
                    return await send_method(
                        chat_id, self.attachments[0],
                        caption=self.text, reply_markup=self.keyboard, **kwargs)
        else:
            return await bot.send_message(
                chat_id, self.text,
                reply_markup=self.keyboard, **kwargs)


@dataclass
class FutureScene:
    class_name: Optional[str]
    scene_name: str


class AttachmentType:
    PHOTO = 'photo'
    VIDEO = 'video'
    ANIMATION = 'animation'
    DOCUMENT = 'document'
    AUDIO = 'audio'
    STICKER = 'sticker'


class EventType:
    MESSAGE = 'message'
    CALLBACK_QUERY = 'callback_query'
    UPDATE = 'update'
    EDITED_MESSAGE = 'edited_message'
    CHANNEL_POST = 'channel_post'
    EDITED_CHANNEL_POST = 'edited_channel_post'
    INLINE_QUERY = 'inline_query'
    CHOSEN_INLINE_RESULT = 'chosen_inline_result'
    SHIPPING_QUERY = 'shipping_query'
    PRE_CHECKOUT_QUERY = 'pre_checkout_query'
    POLL = 'poll'
    POLL_ANSWER = 'poll_answer'
    MY_CHAT_MEMBER = 'my_chat_member'
    CHAT_MEMBER = 'chat_member'

    ALL = (MESSAGE, CALLBACK_QUERY, UPDATE, EDITED_MESSAGE,
           CHANNEL_POST, EDITED_CHANNEL_POST, INLINE_QUERY,
           CHOSEN_INLINE_RESULT, SHIPPING_QUERY, PRE_CHECKOUT_QUERY,
           POLL, POLL_ANSWER, MY_CHAT_MEMBER, CHAT_MEMBER)
