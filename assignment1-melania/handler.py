from abc import ABC, abstractmethod

from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.community import Community
from ipv8.peer import Peer
from messages import ResponseMessage

class MessageHandler(ABC):
    message_class: type[DataClassPayload]

    def __init__(self, community: Community) -> None:
        self.community = community

    @abstractmethod
    def handle(self, peer: Peer, payload: DataClassPayload) -> None:
        pass



class ResponseHandler(MessageHandler):
    message_class = ResponseMessage

    def handle(self, peer: Peer, payload: ResponseMessage) -> None:
        print("Got a message from:", peer)
        print(f"Got a message with success: {payload.success}, with the message:\n", payload.message)
