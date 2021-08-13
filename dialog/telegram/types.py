from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Optional, Sequence, Tuple, Union

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputFile, MediaGroup
from aiogram.types import Message as AiogramMessage
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from dialog import bases
from dialog.shared.utils import is_url


@dataclass
class Message(bases.BaseMessage):
    text: Optional[str] = None

    attachment_type: Optional[str] = None
    attachments: Optional[Sequence[str]] = None

    keyboard: Optional[Union[ReplyKeyboardMarkup,
                             InlineKeyboardMarkup,
                             ReplyKeyboardRemove]] = None

    def __post_init__(self):
        self._custom_messages = self.convert_to_custom_message()

    def convert_to_custom_message(self) -> Tuple['CustomMessage']:
        custom_messages = []

        if self.attachment_type and self.attachments:
            if len(self.attachments) > 1:
                if self.attachment_type == AttachmentType.STICKER:
                    if self.text:
                        custom_messages.append(CustomMessage(text=self.text))

                    for attachment in self.attachments[:-1]:
                        custom_messages.append(CustomMessage(sticker=attachment))

                    custom_messages.append(CustomMessage(sticker=self.attachments[-1],
                                                         reply_markup=self.keyboard))

                elif self.attachment_type == AttachmentType.ANIMATION:
                    for attachment in self.attachments[:-1]:
                        custom_messages.append(CustomMessage(animation=attachment))

                    custom_messages.append(CustomMessage(animation=self.attachments[-1],
                                                         caption=self.text,
                                                         reply_markup=self.keyboard))
                else:
                    """Если вложений > 1. Отправка медиа группы"""
                    media_group = MediaGroup()
                    attach_method: Callable = \
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

                    custom_messages.append(CustomMessage(media=media_group))

            else:
                if self.attachment_type == AttachmentType.STICKER:
                    if self.text:
                        custom_messages.append(CustomMessage(text=self.text))

                    custom_messages.append(CustomMessage(sticker=self.attachments[0],
                                                         reply_markup=self.keyboard))
                else:
                    custom_messages.append(CustomMessage(
                        **{self.attachment_type.lower(): self.attachments[0]},
                        caption=self.text, reply_markup=self.keyboard))
        else:
            custom_messages.append(CustomMessage(text=self.text, reply_markup=self.keyboard))

        return tuple(custom_messages)

    async def send(self, chat_id: Union[int, str]):
        for custom_message in self._custom_messages:
            await custom_message.send(chat_id=chat_id)


class CustomMessage(bases.BaseMessage):
    def __init__(self,
                 send_method: Optional[Callable] = None,  # AutoDetect
                 **message_kwargs):
        self.message_kwargs = message_kwargs
        self._send_method = send_method

    @cached_property
    def send_method(self) -> Callable:
        if self._send_method is not None:
            return self._send_method

        bot = Bot.get_current()

        if 'text' in self.message_kwargs:
            return bot.send_message
        elif 'audio' in self.message_kwargs:
            return bot.send_audio
        elif 'animation' in self.message_kwargs:
            return bot.send_animation
        elif 'document' in self.message_kwargs:
            return bot.send_document
        elif 'photo' in self.message_kwargs:
            return bot.send_photo
        elif 'sticker' in self.message_kwargs:
            return bot.send_sticker
        elif 'video' in self.message_kwargs:
            return bot.send_video
        elif 'video_note' in self.message_kwargs:
            return bot.send_video_note
        elif 'voice' in self.message_kwargs:
            return bot.send_voice
        elif 'phone_number' in self.message_kwargs:
            return bot.send_contact
        elif not {'latitude', 'longitude', 'title', 'address'} - set(self.message_kwargs):
            return bot.send_venue
        elif 'latitude' in self.message_kwargs:
            return bot.send_location
        elif not {'question', 'options'} - set(self.message_kwargs):
            return bot.send_poll
        elif 'emoji' in self.message_kwargs:
            return bot.send_dice
        elif 'game_short_name' in self.message_kwargs:
            return bot.send_game
        elif not {'title', 'description', 'payload', 'provider_token', 'currency', 'prices'} - \
                set(self.message_kwargs):
            return bot.send_invoice
        elif 'game_short_name' in self.message_kwargs:
            return bot.send_game
        elif 'media' in self.message_kwargs:
            return bot.send_media_group

    async def send(self, chat_id: Union[str, int]) -> AiogramMessage:
        return await self.send_method(chat_id=chat_id, **self.message_kwargs)


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
