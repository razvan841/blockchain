import asyncio
import sys
from asyncio import run
from ipv8.community import Community, CommunitySettings
from ipv8.configuration import ConfigBuilder, Strategy, WalkerDefinition, default_bootstrap_defs
from ipv8.peer import Peer
from ipv8.util import run_forever
from ipv8_service import IPv8
from handler import ResponseHandler
from sender import SubmitSender
from ipv8.lazy_community import lazy_wrapper
from messages import ResponseMessage, SubmitMessage
from asyncio  import Event

# if sys.platform == "win32":
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


PORT = 8090
EMAIL = "m.d.vartic@student.tudelft.nl"
GITHUB_URL = "https://github.com/melavart"
COMMUNITY_ID = bytes.fromhex("2c1cc6e35ff484f99ebdfb6108477783c0102881")
SERVER_PUBKEY = bytes.fromhex("4c69624e61434c504b3a86b23934a28d669c390e2d1fc0b0870706c4591cc0cb178bc5a811da6d87d27ef319b2638ef60cc8d119724f4c53a1ebfad919c3ac4136c501ce5c09364e0ebb")
NONCE = 2951537872
    

class MiningCommunity(Community):
    community_id = COMMUNITY_ID
    response_event = Event
    
    def __init__(self, settings : CommunitySettings) -> None:
        super().__init__(settings)
        self.handler = ResponseHandler(self)
        self.sender = SubmitSender(self)
        self.add_message_handler(ResponseMessage, self.on_message)
        self.add_message_handler(SubmitMessage, self.on_submit)
        self.server: Peer | None = None
        self.submitted = False

    def started(self) -> None:
        self.network.add_peer_observer(self)

    def on_peer_added(self, peer: Peer):
        peer_key = peer.public_key.key_to_bin()
        print(f"Peer: {peer}")
        print(f"  their key : {peer_key.hex()}")
        print(f"  server key: {SERVER_PUBKEY.hex()}")
        print(f"  match: {peer_key == SERVER_PUBKEY}")
        if peer_key == SERVER_PUBKEY and not self.submitted:
            print(f"Found server: {peer}")
            self.server = peer
            self.sender.send(peer, SubmitMessage(EMAIL, GITHUB_URL, NONCE))
            self.submitted = True
            print("Submission sent to server, waiting for response...")
            self.cancel_all_pending_tasks()
    
    def on_peer_remove(self, peer: Peer):
        if peer == self.server:
            self.server = None


    @lazy_wrapper(ResponseMessage)
    def on_message(self, peer: Peer, payload: ResponseMessage) -> None:
        self.handler.handle(peer, payload)

    @lazy_wrapper(SubmitMessage)
    def on_submit(self, peer: Peer, payload: SubmitMessage) -> None:
        print("Got a message from:", peer)
        print(f"Got a message with nonce: {payload.nonce}, with the email: {payload.email} and github: {payload.github_url}")


async def start_community() -> None:
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.add_key(EMAIL, "curve25519", "client.pem")
    builder.add_overlay("MiningCommunity", EMAIL,
                            [WalkerDefinition(Strategy.RandomWalk, 10, {"timeout": 3.0})],
                            default_bootstrap_defs, {}, [("started",)]
                            )
    await IPv8(builder.finalize(), extra_communities={"MiningCommunity": MiningCommunity}).start()
    await run_forever()


run(start_community())

