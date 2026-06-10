import asyncio
import threading

from ipv8.community import Community
from ipv8.lazy_community import lazy_wrapper
from ipv8.keyvault.crypto import default_eccrypto

from config import COMMUNITY_ID, DIFFICULTY, SERVER_KEY_HEX
from models import (
    Block,
    BlockMsg,
    BlockResponse,
    ChainHeightResponse,
    GENESIS,
    GetBlock,
    GetChainHeight,
    SubmitTransaction,
    SubmitTransactionResponse,
    TxMsg,
)
from primitives import (
    _mine_block_sync,
    compute_block_hash,
    compute_tx_hash,
    leading_zero_bits,
    sha256,
)


class BlockchainCommunity(Community):
    community_id = COMMUNITY_ID

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.blocks: dict[bytes, Block] = {GENESIS.block_hash: GENESIS}
        self.tip: Block = GENESIS
        self.orphans: dict[bytes, Block] = {}
        self.mempool: list[bytes] = []

        self._mining = False
        self._stop_mining = threading.Event()

        self.add_message_handler(SubmitTransaction, self.on_submit_tx)
        self.add_message_handler(GetChainHeight, self.on_get_height)
        self.add_message_handler(GetBlock, self.on_get_block)
        self.add_message_handler(BlockResponse, self.on_block_response)
        self.add_message_handler(TxMsg, self.on_tx_msg)
        self.add_message_handler(BlockMsg, self.on_block_msg)

        print(f"[blockchain] initialized  community={COMMUNITY_ID.hex()[:16]}")

    def started(self):
        print("[blockchain] started — registering mine and sync tasks")
        self.register_task("mine", self.mine_loop, interval=0.1)
        self.register_task("sync", self.sync_chain, interval=5.0)

    def _is_server(self, peer) -> bool:
        return peer.public_key.key_to_bin().hex() == SERVER_KEY_HEX

    def _peer_id(self, peer) -> str:
        return peer.public_key.key_to_bin().hex()[:12]

    def _validate_block(self, block: Block, parent: Block) -> bool:
        if block.height != parent.height + 1:
            print(f"[validate] FAIL height mismatch  block={block.height}  expected={parent.height + 1}")
            return False
        if block.prev_hash != parent.block_hash:
            print(f"[validate] FAIL prev_hash mismatch at height={block.height}")
            return False
        computed = sha256(b"".join(block.tx_hashes))
        if computed != block.txs_hash:
            print(f"[validate] FAIL txs_hash mismatch at height={block.height}"
                  f"  computed={computed.hex()[:16]}  header={block.txs_hash.hex()[:16]}")
            return False
        h = compute_block_hash(block.prev_hash, block.txs_hash, block.timestamp,
                               block.difficulty, block.nonce)
        zeros = leading_zero_bits(h)
        if zeros < block.difficulty:
            print(f"[validate] FAIL PoW at height={block.height}"
                  f"  zeros={zeros}  required={block.difficulty}")
            return False
        print(f"[validate] OK height={block.height}  zeros={zeros}  txs={len(block.tx_hashes)}")
        return True

    def _get_canonical_block(self, height: int) -> Block | None:
        if height > self.tip.height:
            return None
        b = self.tip
        while b.height > height:
            parent = self.blocks.get(b.prev_hash)
            if parent is None:
                return None
            b = parent
        return b if b.height == height else None

    def _update_mempool(self):
        before = len(self.mempool)
        confirmed: set[bytes] = set()
        b = self.tip
        while True:
            for h in b.tx_hashes:
                confirmed.add(h)
            if b.height == 0:
                break
            parent = self.blocks.get(b.prev_hash)
            if parent is None:
                break
            b = parent
        self.mempool = [tx for tx in self.mempool if tx not in confirmed]
        after = len(self.mempool)
        print(f"[mempool] updated  before={before}  after={after}  removed={before - after}")

    def _broadcast_block(self, block: Block, skip_peer=None):
        raw = b"".join(block.tx_hashes)
        msg = BlockMsg(block.height, block.prev_hash, block.txs_hash,
                       block.timestamp, block.difficulty, block.nonce, raw)
        targets = [p for p in self.get_peers() if p != skip_peer and not self._is_server(p)]
        for peer in targets:
            self.ez_send(peer, msg)
        skip_label = self._peer_id(skip_peer) if skip_peer else "none"
        print(f"[broadcast] height={block.height}  sent_to={len(targets)}  skipped={skip_label}")

    def _try_apply(self, block: Block, source_peer=None):
        source = self._peer_id(source_peer) if source_peer else "self"

        if block.block_hash in self.blocks:
            print(f"[try-apply] DUPLICATE height={block.height}"
                  f"  hash={block.block_hash.hex()[:16]}  from={source}")
            return

        parent = self.blocks.get(block.prev_hash)
        if parent is None:
            self.orphans[block.block_hash] = block
            print(f"[try-apply] ORPHAN height={block.height}"
                  f"  hash={block.block_hash.hex()[:16]}"
                  f"  missing_parent={block.prev_hash.hex()[:16]}"
                  f"  from={source}  total_orphans={len(self.orphans)}")
            if source_peer is not None:
                print(f"[try-apply] requesting missing height={block.height - 1} from {source}")
                self.ez_send(source_peer, GetBlock(block.height - 1))
            return

        print(f"[try-apply] validating height={block.height}"
              f"  hash={block.block_hash.hex()[:16]}  from={source}")
        if not self._validate_block(block, parent):
            print(f"[try-apply] REJECTED height={block.height}  from={source}")
            return

        self.blocks[block.block_hash] = block
        print(f"[try-apply] stored height={block.height}  total_blocks={len(self.blocks)}")

        if block.height > self.tip.height:
            old_height = self.tip.height
            self.tip = block
            self._update_mempool()
            self._stop_mining.set()
            print(f"[chain] NEW TIP height={block.height}  was={old_height}"
                  f"  hash={block.block_hash.hex()[:16]}  mempool={len(self.mempool)}")
            self._broadcast_block(block, skip_peer=source_peer)
        else:
            print(f"[try-apply] FORK stored height={block.height}"
                  f"  tip={self.tip.height}  hash={block.block_hash.hex()[:16]}")

        resolved = [o for o in self.orphans.values() if o.prev_hash == block.block_hash]
        if resolved:
            print(f"[try-apply] resolving {len(resolved)} orphan(s) waiting on height={block.height}")
        for orphan in resolved:
            del self.orphans[orphan.block_hash]
            self._try_apply(orphan, source_peer=None)

    async def mine_loop(self):
        if self._mining:
            return
        self._mining = True
        self._stop_mining.clear()
        try:
            prev = self.tip
            txs = list(self.mempool)
            print(f"[mine] starting on prev_height={prev.height}"
                  f"  mempool={len(txs)}  blocks_known={len(self.blocks)}")

            loop = asyncio.get_running_loop()
            block = await loop.run_in_executor(
                None, _mine_block_sync, prev, txs, DIFFICULTY, self._stop_mining
            )

            if block is None:
                print(f"[mine] interrupted — tip is now height={self.tip.height}")
                return

            print(f"[mine] applying self-mined block height={block.height}  nonce={block.nonce}")
            self._try_apply(block, source_peer=None)
        finally:
            self._mining = False

    @lazy_wrapper(BlockMsg)
    def on_block_msg(self, peer, payload):
        tx_count = len(payload.tx_hashes) // 32
        print(f"[recv] BlockMsg height={payload.height}  txs={tx_count}"
              f"  difficulty={payload.difficulty}  from={self._peer_id(peer)}")
        txs = [payload.tx_hashes[i:i + 32] for i in range(0, len(payload.tx_hashes), 32)]
        block = Block(payload.height, payload.prev_hash, payload.txs_hash,
                      payload.timestamp, payload.difficulty, payload.nonce, txs)
        self._try_apply(block, source_peer=peer)

    @lazy_wrapper(BlockResponse)
    def on_block_response(self, peer, payload):
        tx_count = len(payload.tx_hashes) // 32
        print(f"[recv] BlockResponse height={payload.height}  txs={tx_count}"
              f"  from={self._peer_id(peer)}")
        txs = [payload.tx_hashes[i:i + 32] for i in range(0, len(payload.tx_hashes), 32)]
        block = Block(payload.height, payload.prev_hash, payload.txs_hash,
                      payload.timestamp, payload.difficulty, payload.nonce, txs)
        self._try_apply(block, source_peer=peer)

    @lazy_wrapper(SubmitTransaction)
    def on_submit_tx(self, peer, payload):
        sender_label = "server" if self._is_server(peer) else self._peer_id(peer)
        print(f"[recv] SubmitTransaction from={sender_label}"
              f"  data_len={len(payload.data)}  sender_key={payload.sender_key.hex()[:16]}")

        key = default_eccrypto.key_from_public_bin(payload.sender_key)
        msg_bytes = (payload.sender_key
                     + payload.data
                     + payload.timestamp.to_bytes(8, "big"))
        ok = default_eccrypto.is_valid_signature(key, msg_bytes, payload.signature)
        h = compute_tx_hash(payload.sender_key, payload.data,
                            payload.timestamp, payload.signature)

        print(f"[submit-tx] sig_valid={ok}  tx_hash={h.hex()[:16]}")

        if ok:
            if h not in self.mempool:
                self.mempool.append(h)
                print(f"[submit-tx] added to mempool  size={len(self.mempool)}")
                targets = [p for p in self.get_peers() if p != peer and not self._is_server(p)]
                for p in targets:
                    self.ez_send(p, TxMsg(payload.sender_key, payload.data,
                                          payload.timestamp, payload.signature))
                print(f"[submit-tx] forwarded TxMsg to {len(targets)} peer(s)")
            else:
                print(f"[submit-tx] duplicate — already in mempool")
        else:
            print(f"[submit-tx] REJECTED bad signature")

        self.ez_send(peer, SubmitTransactionResponse(ok, h, "accepted" if ok else "bad signature"))
        print(f"[submit-tx] sent response success={ok}")

    @lazy_wrapper(TxMsg)
    def on_tx_msg(self, peer, payload):
        h = compute_tx_hash(payload.sender_key, payload.data,
                            payload.timestamp, payload.signature)
        if h not in self.mempool:
            self.mempool.append(h)
            print(f"[recv] TxMsg NEW tx_hash={h.hex()[:16]}"
                  f"  from={self._peer_id(peer)}  mempool={len(self.mempool)}")
        else:
            print(f"[recv] TxMsg DUPLICATE tx_hash={h.hex()[:16]}  from={self._peer_id(peer)}")

    @lazy_wrapper(GetChainHeight)
    def on_get_height(self, peer, payload):
        label = "server" if self._is_server(peer) else self._peer_id(peer)
        print(f"[recv] GetChainHeight from={label}  request_id={payload.request_id}"
              f"  -> height={self.tip.height}  tip_hash={self.tip.block_hash.hex()[:16]}")
        self.ez_send(peer, ChainHeightResponse(
            payload.request_id, self.tip.height, self.tip.block_hash
        ))

    @lazy_wrapper(GetBlock)
    def on_get_block(self, peer, payload):
        label = "server" if self._is_server(peer) else self._peer_id(peer)
        b = self._get_canonical_block(payload.height)
        if b is None:
            print(f"[recv] GetBlock from={label}  height={payload.height}"
                  f"  -> NOT FOUND  tip={self.tip.height}")
            return
        print(f"[recv] GetBlock from={label}  height={payload.height}"
              f"  -> hash={b.block_hash.hex()[:16]}  txs={len(b.tx_hashes)}")
        self.ez_send(peer, BlockResponse(
            b.height, b.prev_hash, b.txs_hash, b.timestamp,
            b.difficulty, b.nonce, b.block_hash,
            b"".join(b.tx_hashes)
        ))

    async def sync_chain(self):
        peers = [p for p in self.get_peers() if not self._is_server(p)]
        next_height = self.tip.height + 1
        if peers:
            print(f"[sync] requesting height={next_height} from {len(peers)} peer(s)"
                  f"  tip={self.tip.height}  orphans={len(self.orphans)}")
            for peer in peers:
                self.ez_send(peer, GetBlock(next_height))
        else:
            print(f"[sync] no peers available  tip={self.tip.height}")
