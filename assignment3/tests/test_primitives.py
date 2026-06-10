import hashlib
import threading
import pytest
from primitives import (
    _mine_block_sync,
    compute_block_hash,
    compute_tx_hash,
    leading_zero_bits,
    sha256,
)

def test_sha256_matches_hashlib():
    assert sha256(b"hello") == hashlib.sha256(b"hello").digest()
    assert sha256(b"") == hashlib.sha256(b"").digest()


@pytest.mark.parametrize("data, expected", [
    (b"\x00", 8),
    (b"\x00\x00", 16),
    (b"\x80", 0),          # high bit set -> no leading zero bits
    (b"\x01", 7),          # 0000 0001 -> 7 leading zeros
    (b"\x00\x01", 15),     # 8 + 7
    (b"\xff", 0),
])

def test_leading_zero_bits(data, expected):
    assert leading_zero_bits(data) == expected

def test_leading_zero_bits_all_zero_full_hash():
    assert leading_zero_bits(b"\x00" * 32) == 256

def test_compute_tx_hash_is_deterministic_and_field_sensitive():
    base = compute_tx_hash(b"key", b"data", 123, b"sig")
    assert base == compute_tx_hash(b"key", b"data", 123, b"sig")
    assert base != compute_tx_hash(b"key", b"data", 124, b"sig")
    assert base != compute_tx_hash(b"KEY", b"data", 123, b"sig")
    assert base != compute_tx_hash(b"key", b"data2", 123, b"sig")
    assert base != compute_tx_hash(b"key", b"data", 123, b"sig2")

def test_compute_tx_hash_layout():
    expected = sha256(b"key" + b"data" + (123).to_bytes(8, "big") + b"sig")
    assert compute_tx_hash(b"key", b"data", 123, b"sig") == expected

def test_compute_block_hash_is_deterministic_and_nonce_sensitive():
    prev = b"\x11" * 32
    txs = b"\x22" * 32
    h0 = compute_block_hash(prev, txs, 1000, 8, 0)
    assert h0 == compute_block_hash(prev, txs, 1000, 8, 0)
    assert h0 != compute_block_hash(prev, txs, 1000, 8, 1)
    assert h0 != compute_block_hash(prev, txs, 1001, 8, 0)
    assert h0 != compute_block_hash(prev, txs, 1000, 9, 0)

def test_mine_block_sync_produces_valid_pow():
    from models import GENESIS

    difficulty = 8
    stop = threading.Event()
    block = _mine_block_sync(GENESIS, [], difficulty, stop)

    assert block is not None
    assert block.height == GENESIS.height + 1
    assert block.prev_hash == GENESIS.block_hash
    assert block.difficulty == difficulty
    assert block.txs_hash == sha256(b"")
    assert leading_zero_bits(block.block_hash) >= difficulty
    assert block.block_hash == compute_block_hash(
        block.prev_hash, block.txs_hash, block.timestamp,
        block.difficulty, block.nonce,
    )

def test_mine_block_sync_includes_transactions():
    from models import GENESIS

    txs = [b"\xaa" * 32, b"\xbb" * 32]
    block = _mine_block_sync(GENESIS, txs, 4, threading.Event())

    assert block is not None
    assert block.tx_hashes == txs
    assert block.txs_hash == sha256(b"".join(txs))

def test_mine_block_sync_respects_stop_event():
    from models import GENESIS

    stop = threading.Event()
    stop.set()
    assert _mine_block_sync(GENESIS, [], 8, stop) is None
