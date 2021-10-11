from dataclasses import dataclass
from functools import cached_property
from io import BytesIO
from typing import Callable, List, Optional, Sequence, Tuple, Union

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InputFile, MediaGroup
from aiogram.types import Message as AiogramMessage
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from dialog import bases
from dialog.shared.utils import is_url


@dataclass
class SimpleMessage(bases.BaseMessage):
    text: Optional[str] = None

    attachment_type: Optional[str] = None
    attachments: Optional[Sequence[Union[str, BytesIO]]] = None

    keyboard: Optional[Union[ReplyKeyboardMarkup, InlineKeyboardMarkup, ReplyKeyboardRemove]] = None

    def __post_init__(self):
        self._default_messages = self._convert_to_default_message()

    def _convert_to_default_message(self) -> Tuple['Message', ...]:
        default_messages: List[Message] = []

        if self.attachment_type and self.attachments:
            if len(self.attachments) > 1:
                if self.attachment_type == AttachmentType.STICKER:
                    if self.text:
                        default_messages.append(Message(text=self.text))

                    for attachment in self.attachments[:-1]:
                        default_messages.append(Message(sticker=attachment))

                    default_messages.append(Message(sticker=self.attachments[-1],
                                                    reply_markup=self.keyboard))
                elif self.attachment_type == AttachmentType.ANIMATION:
                    for attachment in self.attachments[:-1]:
                        default_messages.append(Message(animation=attachment))

                    default_messages.append(Message(animation=self.attachments[-1],
                                                    caption=self.text,
                                                    reply_markup=self.keyboard))
                else:
                    """If attachments > 1: media group"""
                    media_group = MediaGroup()
                    attach_method: Callable = \
                        getattr(media_group, f'attach_{self.attachment_type.lower()}', None)

                    if attach_method is None:
                        raise ValueError(f'Cant attach "{self.attachment_type}" to media group')

                    if isinstance(self.attachments[0], str) and is_url(self.attachments[0]):
                        attach_method(InputFile.from_url(url=self.attachments[0]), self.text)
                    else:
                        attach_method(InputFile(path_or_bytesio=self.attachments[0]), self.text)

                    for attachment in self.attachments[1:]:
                        if is_url(attachment):  # type: ignore  # TODO: change type
                            attach_method(InputFile.from_url(url=attachment))
                        else:
                            attach_method(InputFile(path_or_bytesio=attachment))

                    default_messages.append(Message(media=media_group))
            else:
                if self.attachment_type == AttachmentType.STICKER:
                    if self.text:
                        default_messages.append(Message(text=self.text))

                    default_messages.append(Message(sticker=self.attachments[0],
                                                    reply_markup=self.keyboard))
                else:
                    default_messages.append(
                        Message(**{self.attachment_type.lower(): self.attachments[0]},  # type: ignore
                                caption=self.text,
                                reply_markup=self.keyboard))
        else:
            default_messages.append(Message(text=self.text, reply_markup=self.keyboard))

        return tuple(default_messages)

    async def send(self, chat_id: Union[int, str]) -> List[AiogramMessage]:  # type: ignore
        sent_messages: List[AiogramMessage] = []
        for default_message in self._default_messages:
            sent_messages.append(
                await default_message.send(chat_id=chat_id)
            )

        return sent_messages


class Message(bases.BaseMessage):
    def __init__(self, send_method: Optional[Callable] = None, **message_kwargs):
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

        raise ValueError("Can't detect `send_method`. Specify it explicitly.")

    async def send(self, chat_id: Union[str, int]) -> AiogramMessage:  # type: ignore
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

    ALL = (
        MESSAGE,
        CALLBACK_QUERY,
        UPDATE,
        EDITED_MESSAGE,
        CHANNEL_POST,
        EDITED_CHANNEL_POST,
        INLINE_QUERY,
        CHOSEN_INLINE_RESULT,
        SHIPPING_QUERY,
        PRE_CHECKOUT_QUERY,
        POLL,
        POLL_ANSWER,
        MY_CHAT_MEMBER,
        CHAT_MEMBER,
    )
