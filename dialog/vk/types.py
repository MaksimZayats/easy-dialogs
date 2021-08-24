from typing import List, Optional

from dialog.bases import BaseMessage
from dialog.vk.utils import get_current_bot


class Message(BaseMessage):
    def __init__(self,
                 message: Optional[str] = None,
                 attachment: Optional[str] = None,
                 user_id: Optional[int] = None,
                 domain: Optional[str] = None,
                 chat_id: Optional[int] = None,
                 random_id: Optional[int] = 0,
                 user_ids: Optional[List[int]] = None,
                 lat: Optional[float] = None,
                 long: Optional[float] = None,
                 reply_to: Optional[int] = None,
                 forward_messages: Optional[List[int]] = None,
                 forward: Optional[str] = None,
                 sticker_id: Optional[int] = None,
                 group_id: Optional[int] = None,
                 keyboard: Optional[str] = None,
                 payload: Optional[str] = None,
                 dont_parse_links: Optional[bool] = None,
                 disable_mentions: Optional[bool] = None,
                 template: Optional[str] = None,
                 intent: Optional[str] = None,
                 **kwargs):
        locals().update(kwargs)
        locals().pop('kwargs')
        self.message_config = {key: value for key, value in locals().items()
                               if key != 'self' and value is not None}

    async def send(self, peer_id: int) -> int:
        self.message_config['peer_id'] = peer_id

        return (await get_current_bot().api.request('messages.send', self.message_config))['response']


class EventType:
    MESSAGE = 'message'

    ALL = (MESSAGE,)
