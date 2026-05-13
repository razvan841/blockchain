import asyncio
from dataclasses import dataclass

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.configuration import (
    Bootstrapper,
    BootstrapperDefinition,
    ConfigBuilder,
    DISPERSY_BOOTSTRAPPER,
    Strategy,
    WalkerDefinition,
)
from ipv8_service import IPv8
from ipv8.messaging.payload import Payload
from ipv8.keyvault.crypto import default_eccrypto


SERVER_KEY_HEX = "4c69624e61434c504b3a82e33614a342774e084af80835838d6dbdb64a537d3ddb6c1d82011a7f101553cda40cf5fa0e0fc23abd0a9c4f81322282c5b34566f6b8401f5f683031e60c96"


def load_my_public_key(path):
    with open(path, "rb") as f:
        key = default_eccrypto.key_from_private_bin(f.read())
    return key.pub().key_to_bin()


MY_PUBLIC_KEY = load_my_public_key("razvan.pem")

GROUP_KEYS = [
    MY_PUBLIC_KEY,
    bytes.fromhex("4c69624e61434c504b3a47aea3e964cb96a72c180f25ab4b3418c9741a144c70b98d20755ca24d00e969014d036700220bba081f9ce2e263d4222d8c574bca44bb70008d919e218f3a9b"),
    bytes.fromhex("4c69624e61434c504b3a427b2ddfe21490c98f2ce55297ea7802ad3d300904fb938429ca8c2093812511c0769f7c31a213e0b07f546cc646b7c7f24b36856b0aa7d795c86a815dc4a649"),
]


class RegisterGroup(Payload):
    msg_id = 1

    format_list = ["varlenH", "varlenH", "varlenH"]

    def __init__(self, member1_key, member2_key, member3_key):
        self.member1_key = member1_key
        self.member2_key = member2_key
        self.member3_key = member3_key

    def to_pack_list(self):
        return [
            ("varlenH", self.member1_key),
            ("varlenH", self.member2_key),
            ("varlenH", self.member3_key),
        ]

    @classmethod
    def from_unpack_list(cls, member1_key, member2_key, member3_key):
        return cls(member1_key, member2_key, member3_key)


class RegisterResponse(Payload):
    msg_id = 2

    format_list = ["?", "varlenH", "varlenH"]

    def __init__(self, success, group_id, message):
        self.success = success
        self.group_id = group_id
        self.message = message

    def to_pack_list(self):
        return [
            ("?", self.success),
            ("varlenH", self.group_id.encode()),
            ("varlenH", self.message.encode()),
        ]

    @classmethod
    def from_unpack_list(cls, success, group_id, message):
        return cls(success, group_id.decode(), message.decode())


class RegistrationCommunity(Community):

    community_id = bytes.fromhex("4c61623247726f75705369676e696e6732303236")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server_peer = None
        self.response_event = asyncio.Event()

        self.add_message_handler(RegisterResponse, self.on_register_response)

    def started(self):
        self.register_task("discover", self.discover_server, interval=1.0)

    def discover_server(self):
        for peer in self.get_peers():
            key = peer.public_key.key_to_bin()

            if key.hex() == SERVER_KEY_HEX:
                self.server_peer = peer
                print("Server found")

        if self.server_peer:
            self.cancel_pending_task("discover")
            self.register_group()

    def register_group(self):
        print("Send registration")

        self.ez_send(
            self.server_peer,
            RegisterGroup(
                GROUP_KEYS[0],
                GROUP_KEYS[1],
                GROUP_KEYS[2],
            )
        )

    @lazy_wrapper(RegisterResponse)
    def on_register_response(self, peer, payload):
        print("\n===== SERVER RESPONSE =====")
        print("Success:", payload.success)
        print("Message:", payload.message)
        print("Group ID:", payload.group_id)
        print("===========================\n")

        self.response_event.set()


async def main():
    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.add_key("mykey", "curve25519", "razvan.pem")

    builder.add_overlay(
        "RegistrationCommunity",
        "mykey",
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

    ipv8 = IPv8(builder.finalize(), extra_communities={"RegistrationCommunity": RegistrationCommunity})
    await ipv8.start()

    community = next(c for c in ipv8.overlays if isinstance(c, RegistrationCommunity))
    await community.response_event.wait()

    await ipv8.stop()


if __name__ == "__main__":
    asyncio.run(main())