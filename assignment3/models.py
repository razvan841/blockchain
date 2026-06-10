from ipv8.messaging.lazy_payload import VariablePayloadWID
from primitives import compute_block_hash, sha256


# --- Registration messages ---

class RegisterBlockchain(VariablePayloadWID):
    msg_id = 1
    format_list = ["varlenHutf8", "varlenH"]
    names = ["group_id", "community_id"]


class RegisterResponse(VariablePayloadWID):
    msg_id = 2
    format_list = ["?", "varlenHutf8"]
    names = ["success", "message"]


# --- Client <-> server transaction / query messages ---

class SubmitTransaction(VariablePayloadWID):
    msg_id = 1
    format_list = ["varlenH", "varlenH", "q", "varlenH"]
    names = ["sender_key", "data", "timestamp", "signature"]


class SubmitTransactionResponse(VariablePayloadWID):
    msg_id = 2
    format_list = ["?", "varlenH", "varlenHutf8"]
    names = ["success", "tx_hash", "message"]


class GetChainHeight(VariablePayloadWID):
    msg_id = 3
    format_list = ["q"]
    names = ["request_id"]


class ChainHeightResponse(VariablePayloadWID):
    msg_id = 4
    format_list = ["q", "q", "varlenH"]
    names = ["request_id", "height", "tip_hash"]


class GetBlock(VariablePayloadWID):
    msg_id = 5
    format_list = ["q"]
    names = ["height"]


class BlockResponse(VariablePayloadWID):
    msg_id = 6
    format_list = ["q", "varlenH", "varlenH", "q", "q", "q", "varlenH", "varlenH"]
    names = ["height", "prev_hash", "txs_hash", "timestamp", "difficulty", "nonce", "block_hash", "tx_hashes"]


# --- Peer-to-peer gossip messages ---

class TxMsg(VariablePayloadWID):
    msg_id = 10
    format_list = ["varlenH", "varlenH", "Q", "varlenH"]
    names = ["sender_key", "data", "timestamp", "signature"]


class BlockMsg(VariablePayloadWID):
    msg_id = 11
    format_list = ["I", "32s", "32s", "Q", "I", "Q", "varlenH"]
    names = ["height", "prev_hash", "txs_hash", "timestamp", "difficulty", "nonce", "tx_hashes"]


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