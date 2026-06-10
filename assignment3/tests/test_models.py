from models import (
    GENESIS,
    Block,
    BlockMsg,
    ChainHeightResponse,
    SubmitTransaction,
)
from primitives import compute_block_hash, sha256


def test_block_hash_is_derived_from_header():
    block = Block(
        height=1,
        prev_hash=b"\x01" * 32,
        txs_hash=b"\x02" * 32,
        timestamp=1234,
        difficulty=8,
        nonce=42,
        tx_hashes=[b"\x03" * 32],
    )
    assert block.block_hash == compute_block_hash(
        b"\x01" * 32, b"\x02" * 32, 1234, 8, 42,
    )

def test_block_stores_all_fields():
    txs = [b"\xab" * 32]
    block = Block(2, b"\x00" * 32, sha256(b""), 99, 4, 7, txs)
    assert block.height == 2
    assert block.prev_hash == b"\x00" * 32
    assert block.txs_hash == sha256(b"")
    assert block.timestamp == 99
    assert block.difficulty == 4
    assert block.nonce == 7
    assert block.tx_hashes is txs

def test_genesis_is_well_formed():
    assert GENESIS.height == 0
    assert GENESIS.prev_hash == b"\x00" * 32
    assert GENESIS.txs_hash == sha256(b"")
    assert GENESIS.difficulty == 0
    assert GENESIS.nonce == 0
    assert GENESIS.tx_hashes == []
    assert GENESIS.block_hash == compute_block_hash(
        b"\x00" * 32, sha256(b""), 0, 0, 0,
    )

def test_genesis_is_stable_across_imports():
    recomputed = Block(0, b"\x00" * 32, sha256(b""), 0, 0, 0, [])
    assert recomputed.block_hash == GENESIS.block_hash

def test_message_dataclasses_carry_fields_and_ids():
    tx = SubmitTransaction(b"key", b"data", 5, b"sig")
    assert (tx.sender_key, tx.data, tx.timestamp, tx.signature) == (b"key", b"data", 5, b"sig")
    assert SubmitTransaction.msg_id == 1

    resp = ChainHeightResponse(7, 3, b"\x09" * 32)
    assert (resp.request_id, resp.height, resp.tip_hash) == (7, 3, b"\x09" * 32)
    assert ChainHeightResponse.msg_id == 4

    blk = BlockMsg(3, b"\x00" * 32, sha256(b""), 1, 8, 2, b"")
    assert blk.height == 3
    assert BlockMsg.msg_id == 11
