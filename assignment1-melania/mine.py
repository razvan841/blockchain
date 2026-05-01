from multiprocessing import Process, Event, Queue
import hashlib
import struct
import os


DIFFICULTY = 28
FULL_ZERO_BYTES = DIFFICULTY // 8  
REMAINDER_BYTES = DIFFICULTY % 8 
REMAINDER_MASK  = 0xFF << (8 - REMAINDER_BYTES) & 0xFF
EMAIL = "m.d.vartic@student.tudelft.nl"
GITHUB_URL = "https://github.com/melavart"

def check (digest: bytes ) -> bool:
    if digest[0] | digest[1] | digest[2]:
        return False
    return (digest[3] & REMAINDER_MASK) == 0

def miner(prefix: bytes, start: int, stride: int, stop_event, result_q):
    base = hashlib.sha256(prefix)
    nonce = start
    pack = struct.Struct('>q').pack
    copy = base.copy
    i = 0
    while True:
        h = copy()
        h.update(pack(nonce))
        d = h.digest()
        if (d[0] | d[1] | d[2]) == 0 and (d[3] & 0xF0) == 0:
            result_q.put((nonce, d.hex()))
            stop_event.set()
            return
        nonce += stride
        i += 1
        if i == 10000:
            i = 0
            if stop_event.is_set():
                return


def find_nonce(prefix: bytes) -> tuple[int, str]:
    n_workers = os.cpu_count()
    stop = Event()
    q = Queue()
    workers = []
    start = int.from_bytes(os.urandom(4), 'big')
    for i in range(n_workers):
        p = Process(target=miner, args=(prefix, start + i, n_workers, stop, q))
        p.start()
        workers.append(p)
    nonce, digest_hex = q.get()
    for p in workers:
        p.terminate()
        p.join()
    return nonce, digest_hex


if __name__ == '__main__':
    prefix = (EMAIL + "\n" + GITHUB_URL + "\n").encode("utf-8")

    nonce, digest_hex = find_nonce(prefix)

    print()
    print("=" * 60)
    print(f"FOUND VALID NONCE")
    print("=" * 60)
    print(f"Nonce (int):    {nonce}")
    print(f"Nonce (hex):    {nonce:016x}")
    print(f"Nonce (bytes):  {struct.pack('>q', nonce).hex()}")
    print(f"Digest:         {digest_hex}")
    print(f"Leading zeros:  {bin(int(digest_hex, 16))[2:].zfill(256).index('1')} bits")