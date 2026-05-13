import asyncio
import time
from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from dataclasses import dataclass
from ipv8.messaging.payload import Payload
from ipv8_service import IPv8
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.configuration import (
    Bootstrapper,
    BootstrapperDefinition,
    ConfigBuilder,
    DISPERSY_BOOTSTRAPPER,
    Strategy,
    WalkerDefinition,
)

GROUP_ID = "80d4b9225f25dcd4"
MY_INDEX = 0
SERVER_KEY_HEX = "4c69624e61434c504b3a82e33614a342774e084af80835838d6dbdb64a537d3ddb6c1d82011a7f101553cda40cf5fa0e0fc23abd0a9c4f81322282c5b34566f6b8401f5f683031e60c96"

def load_my_public_key(path):
    with open(path, "rb") as f:
        key = default_eccrypto.key_from_private_bin(f.read())
    return key.pub().key_to_bin()

MY_PUBLIC_KEY = load_my_public_key("razvan.pem")

GROUP_KEYS = [
    MY_PUBLIC_KEY,
    bytes.fromhex("4c69624e61434c504b3a47aea3e964cb96a72c180f25ab4b3418c9741a144c70b98d20755ca24d00e969014d036700220bba081f9ce2e263d4222d8c574bca44bb70008d919e218f3a9b"),
    bytes.fromhex("4c69624e61434c504b3a33eebeffe4935cec64f15e232fa8c63fb9817633b4617c5a04a08b7e820efb329a9c379ff485ba5244b8f69e1c04900b27d915a0e6c1e54d7d7f301a208a9999"),
]

class ChallengeRequest(Payload):
    msg_id = 3
    format_list = ["varlenH"]

    def __init__(self, group_id):
        self.group_id = group_id

    def to_pack_list(self):
        return [("varlenH", self.group_id.encode())]

    @classmethod
    def from_unpack_list(cls, group_id):
        return cls(group_id.decode())


class ChallengeResponse(Payload):
    msg_id = 4
    format_list = ["varlenH", "q", "d"]

    def __init__(self, nonce, round_number, deadline):
        self.nonce = nonce
        self.round_number = round_number
        self.deadline = deadline

    def to_pack_list(self):
        return [
            ("varlenH", self.nonce),
            ("q", self.round_number),
            ("d", self.deadline),
        ]

    @classmethod
    def from_unpack_list(cls, nonce, round_number, deadline):
        return cls(nonce, round_number, deadline)


class SignatureBundle(Payload):
    msg_id = 5
    format_list = ["varlenH", "q", "varlenH", "varlenH", "varlenH"]

    def __init__(self, group_id, round_number, sig1, sig2, sig3):
        self.group_id = group_id
        self.round_number = round_number
        self.sig1 = sig1
        self.sig2 = sig2
        self.sig3 = sig3

    def to_pack_list(self):
        return [
            ("varlenH", self.group_id.encode()),
            ("q", self.round_number),
            ("varlenH", self.sig1),
            ("varlenH", self.sig2),
            ("varlenH", self.sig3),
        ]

    @classmethod
    def from_unpack_list(cls, group_id, round_number, s1, s2, s3):
        return cls(group_id.decode(), round_number, s1, s2, s3)


class RoundResult(Payload):
    msg_id = 6
    format_list = ["?", "q", "q", "varlenH"]

    def __init__(self, success, round_number, rounds_completed, message):
        self.success = success
        self.round_number = round_number
        self.rounds_completed = rounds_completed
        self.message = message

    def to_pack_list(self):
        return [
            ("?", self.success),
            ("q", self.round_number),
            ("q", self.rounds_completed),
            ("varlenH", self.message.encode()),
        ]

    @classmethod
    def from_unpack_list(cls, success, r, rc, msg):
        return cls(success, r, rc, msg.decode())


class NonceMsg(Payload):
    msg_id = 10
    format_list = ["varlenH", "q"]

    def __init__(self, nonce, round_number):
        self.nonce = nonce
        self.round_number = round_number

    def to_pack_list(self):
        return [("varlenH", self.nonce), ("q", self.round_number)]

    @classmethod
    def from_unpack_list(cls, nonce, r):
        return cls(nonce, r)


class SigMsg(Payload):
    msg_id = 11
    format_list = ["q", "varlenH"]

    def __init__(self, round_number, sig):
        self.round_number = round_number
        self.sig = sig

    def to_pack_list(self):
        return [("q", self.round_number), ("varlenH", self.sig)]

    @classmethod
    def from_unpack_list(cls, r, sig):
        return cls(r, sig)


class HelloMsg(Payload):
    msg_id = 12
    format_list = ["I", "varlenH"]

    def __init__(self, index, pubkey):
        self.index = index
        self.pubkey = pubkey

    def to_pack_list(self):
        return [("I", self.index), ("varlenH", self.pubkey)]

    @classmethod
    def from_unpack_list(cls, i, pk):
        return cls(i, pk)
    
class NextRoundMsg(Payload):
    msg_id = 13
    format_list = ["q"]

    def __init__(self, round_number):
        self.round_number = round_number

    def to_pack_list(self):
        return [("q", self.round_number)]

    @classmethod
    def from_unpack_list(cls, r):
        return cls(r)


class Lab2Community(Community):

    community_id = bytes.fromhex("4c61623247726f75705369676e696e6732303236")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.server_peer = None
        self.peers_by_key = {}
        self.collected_sigs = {}
        self.used_submitters = set()

        self.handshake_received = {}

        self.start_time = time.time()
        self.ready_time = None
        self.round_start_time = None

        self.stable_ticks = 0
        self.handshake_done = False

        self.add_message_handler(ChallengeResponse, self.on_challenge)
        self.add_message_handler(RoundResult, self.on_result)
        self.add_message_handler(NonceMsg, self.on_nonce)
        self.add_message_handler(SigMsg, self.on_sig)
        self.add_message_handler(HelloMsg, self.on_hello)
        self.add_message_handler(NextRoundMsg, self.on_next_round)

    def started(self):
        print(f"[{time.time():.3f}] client started")
        self.register_task("discover", self.find_peers, interval=1.0)

    def find_peers(self):
        for p in self.get_peers():
            key = p.public_key.key_to_bin()

            if key.hex() == SERVER_KEY_HEX:
                self.server_peer = p

            for i, gk in enumerate(GROUP_KEYS):
                if key == gk:
                    self.peers_by_key[i] = p

        print(f"{self.peers_by_key.keys()} {self.server_peer.public_key.key_to_bin().hex() if self.server_peer else None}")
        print(f"[{time.time():.3f}] peers={len(self.peers_by_key)} server={'yes' if self.server_peer else 'no'}")

        if self.server_peer and len(self.peers_by_key) == 2:
            self.stable_ticks += 1
        else:
            self.stable_ticks = 0

        if self.stable_ticks >= 2:
            self.cancel_pending_task("discover")
            self.ready_time = time.time()
            print(f"[{self.ready_time:.3f}] network ready (took {self.ready_time - self.start_time:.3f}s)")
            self.start_handshake()

    def start_handshake(self):
        for i, p in self.peers_by_key.items():
            if i != MY_INDEX:
                print(f"Sent hello to {p.public_key.key_to_bin().hex()}")
                self.ez_send(p, HelloMsg(MY_INDEX, MY_PUBLIC_KEY))
                print(f"Sent hello to {p.public_key.key_to_bin().hex()}")
        self.handshake_received[MY_INDEX] = MY_PUBLIC_KEY

    @lazy_wrapper(HelloMsg)
    def on_hello(self, peer, payload):
        self.handshake_received[payload.index] = payload.pubkey
        print(f"[{time.time():.3f}] received handshake from {peer.public_key.key_to_bin().hex()} (index {payload.index})")
        if len(self.handshake_received) == 3 and not self.handshake_done:
            for i in range(3):
                if i not in self.handshake_received:
                    return
                if self.handshake_received[i] != GROUP_KEYS[i]:
                    print("Handshake failed: key mismatch")
                    return

            self.handshake_done = True
            now = time.time()
            print(f"[{now:.3f}] handshake complete")

            if MY_INDEX == 0:
                self.request_challenge()

    def request_challenge(self):
        self.round_start_time = time.time()
        print(f"[{self.round_start_time:.3f}] requesting challenge")
        self.ez_send(self.server_peer, ChallengeRequest(GROUP_ID))

    @lazy_wrapper(ChallengeResponse)
    def on_challenge(self, peer, payload):
        now = time.time()
        print(f"[{now:.3f}] received challenge round {payload.round_number} (latency {now - self.round_start_time:.3f}s)")

        for i, p in self.peers_by_key.items():
            if i != MY_INDEX:
                self.ez_send(p, NonceMsg(payload.nonce, payload.round_number))

        self.process_nonce(payload.nonce, payload.round_number)

    @lazy_wrapper(NonceMsg)
    def on_nonce(self, peer, payload):
        self.process_nonce(payload.nonce, payload.round_number)

    def process_nonce(self, nonce, round_number):
        sig = default_eccrypto.create_signature(self.my_peer.key, nonce)
        submitter = round_number - 1

        if MY_INDEX == submitter:
            self.collected_sigs[MY_INDEX] = sig
        else:
            self.ez_send(self.peers_by_key[submitter], SigMsg(round_number, sig))

        if MY_INDEX == submitter:
            self.try_submit(round_number)

    @lazy_wrapper(SigMsg)
    def on_sig(self, peer, payload):
        sender_key = peer.public_key.key_to_bin()
        print(f"[{time.time():.3f}] received sig for round {payload.round_number} from {sender_key.hex()}")
        sender_idx = GROUP_KEYS.index(sender_key)
        self.collected_sigs[sender_idx] = payload.sig
        self.try_submit(payload.round_number)

    def try_submit(self, round_number):
        if len(self.collected_sigs) < 3:
            return

        now = time.time()
        print(f"[{now:.3f}] submitting round {round_number} (prep {now - self.round_start_time:.3f}s)")

        sigs = [self.collected_sigs[i] for i in range(3)]

        self.ez_send(self.server_peer,
                     SignatureBundle(GROUP_ID, round_number, *sigs))

        self.used_submitters.add(MY_INDEX)
        self.collected_sigs.clear()

    @lazy_wrapper(RoundResult)
    def on_result(self, peer, payload):
        now = time.time()

        print(
            f"[{now:.3f}] {payload.message} "
            f"(round time {now - self.round_start_time:.3f}s, "
            f"total {now - self.start_time:.3f}s)"
        )

        if not payload.success:
            return

        if payload.rounds_completed == 3:
            print(f"[{now:.3f}] DONE total_time={now - self.start_time:.3f}s")
            return

        next_round = payload.round_number + 1
        next_submitter = next_round - 1

        if next_submitter in self.peers_by_key:
            print(f"[{now:.3f}] notifying peer {next_submitter} to start round {next_round}")

            self.ez_send(
                self.peers_by_key[next_submitter],
                NextRoundMsg(next_round)
            )

    @lazy_wrapper(NextRoundMsg)
    def on_next_round(self, peer, payload):
        print(f"[{time.time():.3f}] received next round trigger for round {payload.round_number}")

        if MY_INDEX == (payload.round_number - 1):
            self.request_challenge()


async def main():
    builder = ConfigBuilder().clear_keys().clear_overlays()

    builder.add_key("mykey", "curve25519", "razvan.pem")

    builder.add_overlay(
        "Lab2Community",
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

    ipv8 = IPv8(builder.finalize(), extra_communities={"Lab2Community": Lab2Community})
    await ipv8.start()
    await asyncio.Event().wait()
    await ipv8.stop()


if __name__ == "__main__":
    asyncio.run(main())