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

from config import COMMUNITY_ID, DIFFICULTY, GROUP_ID, INDEX, PEM_FILE
from models import GENESIS
from blockchain_community import BlockchainCommunity
from registration_community import RegistrationCommunity

async def run():
    print(f"[init] genesis hash={GENESIS.block_hash.hex()}")
    print(f"[init] community={COMMUNITY_ID.hex()}  group={GROUP_ID}  index={INDEX}")
    print(f"[startup] group={GROUP_ID}  index={INDEX}  community={COMMUNITY_ID.hex()}"
          f"  difficulty={DIFFICULTY}  key={PEM_FILE}")

    builder = ConfigBuilder().clear_keys().clear_overlays()
    builder.add_key("mykey", "curve25519", PEM_FILE)

    walker = [WalkerDefinition(Strategy.RandomWalk, 20, {"timeout": 3.0})]
    boot = [BootstrapperDefinition(Bootstrapper.DispersyBootstrapper, dict(DISPERSY_BOOTSTRAPPER["init"]))]

    builder.add_overlay("RegistrationCommunity", "mykey", walker, boot, {}, [("started",)])
    builder.add_overlay("BlockchainCommunity",   "mykey", walker, boot, {}, [("started",)])

    ipv8 = IPv8(
        builder.finalize(),
        extra_communities={
            "RegistrationCommunity": RegistrationCommunity,
            "BlockchainCommunity":   BlockchainCommunity,
        },
    )

    print("[startup] starting IPv8")
    await ipv8.start()

    registration = ipv8.get_overlay(RegistrationCommunity)
    registration.blockchain_community = ipv8.get_overlay(BlockchainCommunity)

    print("[startup] IPv8 running — waiting for peers")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(run())
