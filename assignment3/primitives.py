import hashlib
import threading
import time

def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def leading_zero_bits(h: bytes) -> int:
    n = 0
    for b in h:
        if b == 0:
            n += 8
        else:
            n += 8 - b.bit_length()
            break
    return n

def compute_tx_hash(sender_key: bytes, data: bytes, timestamp: int,
                    signature: bytes) -> bytes:
    return sha256(sender_key + data + timestamp.to_bytes(8, "big") + signature)

def compute_block_hash(prev_hash: bytes, txs_hash: bytes, timestamp: int,
                       difficulty: int, nonce: int) -> bytes:
    return sha256(
        prev_hash
        + txs_hash
        + timestamp.to_bytes(8, "big")
        + difficulty.to_bytes(4, "big")
        + nonce.to_bytes(8, "big")
    )

def _mine_block_sync(prev, txs: list, difficulty: int, stop_event: threading.Event):
    from models import Block

    txs_hash = sha256(b"".join(txs))
    timestamp = int(time.time())
    nonce = 0
    print(f"[mine-thread] starting  prev_height={prev.height}  txs={len(txs)}  difficulty={difficulty}")
    while True:
        if nonce % 10_000 == 0 and stop_event.is_set():
            print(f"[mine-thread] interrupted at nonce={nonce}")
            return None
        h = compute_block_hash(prev.block_hash, txs_hash, timestamp, difficulty, nonce)
        if leading_zero_bits(h) >= difficulty:
            block = Block(prev.height + 1, prev.block_hash, txs_hash,
                          timestamp, difficulty, nonce, txs)
            print(f"[mine-thread] FOUND height={block.height}  nonce={nonce}"
                  f"  zeros={leading_zero_bits(block.block_hash)}  hash={block.block_hash.hex()[:16]}")
            return block
        nonce += 1
