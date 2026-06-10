# Assignment 3 — Proof-of-Work Blockchain over IPv8

## How it works

The node joins two IPv8 overlays at once:

- **RegistrationCommunity** — discovers the course server (matched by its public
  key) and sends it a `RegisterBlockchain` message announcing our group and
  blockchain community id. This is done by only one peer, the one with INDEX = 0
- **BlockchainCommunity** — the actual blockchain. It mines, validates, stores,
  and synchronises blocks with other peers.


## Project layout

| File | Responsibility |
|------|----------------|
| `config.py` | Constants: group id, community id, server key, difficulty, key file. |
| `primitives.py` | Pure hash / proof-of-work helpers and the `_mine_block_sync` worker. No IPv8 dependency. |
| `models.py` | Wire-message dataclasses, the `Block` class, and the `GENESIS` block. |
| `blockchain_community.py` | `BlockchainCommunity` — mining, gossip, validation, fork choice, sync. |
| `registration_community.py` | `RegistrationCommunity` — server discovery and registration. |
| `main.py` | Entry point that configures IPv8 and starts both overlays. |
| `tests/` | Unit tests for the IPv8-free logic (primitives, mining, models). |
| `razvan.pem` | The node's curve25519 key pair. |

## Setup

```bash
pip install -r requirements.txt
```

## Running the node

```bash
# from the assignment3/ directory
python main.py
```

On startup it prints the genesis hash and configuration, starts IPv8, and then
runs until interrupted (`Ctrl+C`). You will see log lines tagged by subsystem,
e.g. `[mine]`, `[try-apply]`, `[chain]`, `[sync]`, `[registration]`.


## Running the tests

The tests cover everything that can be exercised without a live network: the
hash and proof-of-work primitives, the mining worker (real PoW at a low
difficulty), and the `Block` / `GENESIS` / message models.

```bash
# from the assignment3/ directory
python -m pytest tests -q
```



