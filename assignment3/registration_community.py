"""The RegistrationCommunity: finds the server and registers our blockchain."""

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper

from config import COMMUNITY_ID, GROUP_ID, INDEX, MIN_BLOCKCHAIN_PEERS, SERVER_KEY_HEX
from models import RegisterBlockchain, RegisterResponse


class RegistrationCommunity(Community):
    community_id = bytes.fromhex("4c616233426c6f636b636861696e323032365057")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._registered = False
        self.blockchain_community = None
        self.add_message_handler(RegisterResponse, self.on_response)
        print("[registration] initialized")

    def _blockchain_peer_count(self) -> int:
        if self.blockchain_community is None:
            return 0
        return len([
            p for p in self.blockchain_community.get_peers()
            if not self.blockchain_community._is_server(p)
        ])

    def started(self):
        print(f"[registration] started  index={INDEX}  will_register={INDEX == 0}")
        self.register_task("find_server", self.find_and_register, interval=1.0)

    def find_and_register(self):
        if self._registered:
            return
        if INDEX == 0:
            bc_peers = self._blockchain_peer_count()
            if bc_peers < MIN_BLOCKCHAIN_PEERS:
                print(f"[registration] waiting for blockchain peers"
                      f"  have={bc_peers}  need={MIN_BLOCKCHAIN_PEERS}")
                return

            peers = self.get_peers()
            print(f"[registration] scanning {len(peers)} peer(s) for server"
                  f"  blockchain_peers={bc_peers}")
            for peer in peers:
                if peer.public_key.key_to_bin().hex() == SERVER_KEY_HEX:
                    print(f"[registration] server found  key={peer.public_key.key_to_bin().hex()[:16]}")
                    self._registered = True
                    self.cancel_pending_task("find_server")
                    self.ez_send(peer, RegisterBlockchain(GROUP_ID, COMMUNITY_ID))
                    print(f"[registration] sent RegisterBlockchain"
                          f"  group={GROUP_ID}  community={COMMUNITY_ID.hex()}")
                    return

    @lazy_wrapper(RegisterResponse)
    def on_response(self, peer, payload):
        print(f"[registration] response success={payload.success}  message={payload.message!r}")
