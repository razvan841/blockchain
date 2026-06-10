"""Wire-message dataclasses and the in-memory Block representation."""

from dataclasses import dataclass

from primitives import compute_block_hash, sha256


# --- Registration protocol messages ---

@dataclass
class RegisterBlockchain:
    msg_id = 1
    group_id: str
    community_id: bytes


@dataclass
class RegisterResponse:
    msg_id = 2
    success: bool
    message: str


# --- Client <-> server transaction / query messages ---

@dataclass
class SubmitTransaction:
    msg_id = 1
    sender_key: bytes
    data: bytes
    timestamp: int
    signature: bytes


@dataclass
class SubmitTransactionResponse:
    msg_id = 2
    success: bool
    tx_hash: bytes
    message: str


@dataclass
class GetChainHeight:
    msg_id = 3
    request_id: int


@dataclass
class ChainHeightResponse:
    msg_id = 4
    request_id: int
    height: int
    tip_hash: bytes


@dataclass
class GetBlock:
    msg_id = 5
    height: int


@dataclass
class BlockResponse:
    msg_id = 6
    height: int
    prev_hash: bytes
    txs_hash: bytes
    timestamp: int
    difficulty: int
    nonce: int
    block_hash: bytes
    tx_hashes: bytes


# --- Peer-to-peer gossip messages ---

@dataclass
class TxMsg:
    msg_id = 10
    sender_key: bytes
    data: bytes
    timestamp: int
    signature: bytes


@dataclass
class BlockMsg:
    msg_id = 11
    height: int
    prev_hash: bytes
    txs_hash: bytes
    timestamp: int
    difficulty: int
    nonce: int
    tx_hashes: bytes


class Block:
    def __init__(self, height: int, prev_hash: bytes, txs_hash: bytes,
                 timestamp: int, difficulty: int, nonce: int, tx_hashes: list):
        self.height = height
        self.prev_hash = prev_hash
        self.txs_hash = txs_hash
        self.timestamp = timestamp
        self.difficulty = difficulty
        self.nonce = nonce
        self.tx_hashes = tx_hashes
        self.block_hash = compute_block_hash(prev_hash, txs_hash, timestamp, difficulty, nonce)


GENESIS = Block(
    height=0,
    prev_hash=b"\x00" * 32,
    txs_hash=sha256(b""),
    timestamp=0,
    difficulty=0,
    nonce=0,
    tx_hashes=[],
)
