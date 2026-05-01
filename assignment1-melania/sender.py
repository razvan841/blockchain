from abc import ABC
from ipv8.messaging.payload_dataclass import DataClassPayload
from ipv8.community import Community
from ipv8.peer import Peer
from messages import SubmitMessage


class MessageSender(ABC):
    message_class: type[DataClassPayload]

    def __init__(self, community: Community) -> None:
        self.community = community

    def send(self, peer: Peer, payload: DataClassPayload) -> None:
        self.community.ez_send(peer, payload)

class SubmitSender(MessageSender):
    message_class: SubmitMessage

    def __init__(self, community: Community) -> None:
        self.community = community

    def send(self, peer: Peer, payload: SubmitMessage) -> None:
        super().send(peer, payload)
   
    

