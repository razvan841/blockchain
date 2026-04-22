import asyncio
from ipv8.configuration import (
    Bootstrapper,
    BootstrapperDefinition,
    ConfigBuilder,
    DISPERSY_BOOTSTRAPPER,
    Strategy,
    WalkerDefinition,
)
from ipv8_service import IPv8
from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.messaging.payload_dataclass import DataClassPayload, convert_to_payload
from dataclasses import dataclass

EMAIL = "r.p.stefan@tudelft.nl"
GITHUB_URL = "https://github.com/razvan841/blockchain"
NONCE = 30379563

COMMUNITY_ID = bytes.fromhex("2c1cc6e35ff484f99ebdfb6108477783c0102881")

SERVER_PK = bytes.fromhex("4c69624e61434c504b3a86b23934a28d669c390e2d1fc0b0870706c4591cc0cb178bc5a811da6d87d27ef319b2638ef60cc8d119724f4c53a1ebfad919c3ac4136c501ce5c09364e0ebb")

@dataclass
class SubmissionPayload(DataClassPayload[1]):
    email: str
    github_url: str
    nonce: int


@dataclass
class ResponsePayload(DataClassPayload[2]):
    success: bool
    message: str


convert_to_payload(SubmissionPayload)
convert_to_payload(ResponsePayload)


class PowCommunity(Community):
    community_id = COMMUNITY_ID
    response_event: asyncio.Event | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.add_message_handler(ResponsePayload, self.on_response)

    def started(self):
        print("Community started, looking for server...")

        async def task():
            while True:
                peer = self.find_server()
                if peer:
                    print("Found server")
                    self.send_solution(peer)
                    return

                print("Searching...")
                await asyncio.sleep(2)

        self.register_task("find_server", task)

    def find_server(self):
        for peer in self.get_peers():
            if peer.public_key.key_to_bin() == SERVER_PK:
                return peer
        return None

    def send_solution(self, peer):
        payload = SubmissionPayload(EMAIL, GITHUB_URL, NONCE)
        self.ez_send(peer, payload)

    @lazy_wrapper(ResponsePayload)
    def on_response(self, peer, payload):
        print("Server response:")
        print("Success:", payload.success)
        print("Message:", payload.message)

        if self.response_event is not None:
            self.response_event.set()


async def main():
    builder = ConfigBuilder().clear_keys().clear_overlays()
    PowCommunity.response_event = asyncio.Event()

    builder.add_key("my peer", "medium", "ec1.pem")

    builder.add_overlay(
        "PowCommunity",
        "my peer",
        [WalkerDefinition(Strategy.RandomWalk, 20, {"timeout": 3.0})],
        [
            BootstrapperDefinition(
                Bootstrapper.DispersyBootstrapper,
                dict(DISPERSY_BOOTSTRAPPER["init"]),
            )
        ],
        {},
        [("started",)],
    )

    ipv8 = IPv8(builder.finalize(), extra_communities={"PowCommunity": PowCommunity})

    await ipv8.start()
    await PowCommunity.response_event.wait()
    await ipv8.stop()


if __name__ == "__main__":
    asyncio.run(main())