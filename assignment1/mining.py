import hashlib
import time

EMAIL = "r.p.stefan@tudelft.nl"
GITHUB_URL = "https://github.com/razvan841/blockchain"

def has_valid_difficulty(h: bytes) -> bool:
    return h[0] == 0 and h[1] == 0 and h[2] == 0 and h[3] < 16


def mine(email: str, url: str) -> int:
    email_b = email.encode("utf-8")
    url_b = url.encode("utf-8")

    prefix = email_b + b"\n" + url_b + b"\n"

    nonce = 0
    start_time = time.time()

    while True:
        nonce_bytes = nonce.to_bytes(8, "big", signed=True)

        h = hashlib.sha256(prefix + nonce_bytes).digest()

        if has_valid_difficulty(h):
            elapsed = time.time() - start_time
            print("Nonce:", nonce)
            print("Hash:", h.hex())
            print(f"Time: {elapsed:.2f} seconds")
            return nonce
        nonce += 1


if __name__ == "__main__":
    print("Starting mining...")
    result = mine(EMAIL, GITHUB_URL)
    print("Done. Nonce =", result)