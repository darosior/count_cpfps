"""
A quick script to measure the use of CPFP in past blocks. This script requires a local bitcoind
in the default datadir. It's inefficient but may be useful to get an idea of the CPFP usage in a given
historical period.

Note this script tracks ancestor and descendants but does not try to compute whether a (set of)
child incentivized the inclusion of a (set of) parent(s) in the block. It's simply to get an idea
of how much transaction chains are used in practice.
"""

import os
import sys
from authproxy import AuthServiceProxy

# Block range to be inspected.
START_BLOCK_HEIGHT = 799_151
STOP_BLOCK_HEIGHT = 799_251

# Connect to a locally ran bitcoind in the default datadir.
cookie_path = os.path.join(os.getenv("HOME"), ".bitcoin", ".cookie")
with open(cookie_path) as fd:
    authpair = fd.read()
endpoint = f"http://{authpair}@localhost:8332"
rpc = AuthServiceProxy(endpoint)

# Data we're interested in.
total_transactions = 0
total_child_count = 0
total_parent_count = 0
min_child_percentage = None
max_child_percentage = 0
min_parent_percentage = None
max_parent_percentage = 0
candidate_count = 0  # Number of transactions that would be considered for fee estimation.
candidate_parent_count = 0  # Number of them that have a child in the same block.

# For each block within the given range, go through the list of transactions and record
# which one have child or parent in the same block.
for height in range(START_BLOCK_HEIGHT, STOP_BLOCK_HEIGHT + 1):
    perc_done = (height - START_BLOCK_HEIGHT + 1) / (STOP_BLOCK_HEIGHT - START_BLOCK_HEIGHT + 1) * 100
    print(f"At block {height} ({int(perc_done)}% done).", end='\r')
    block_hash = rpc.getblockhash(height)
    block_txs = rpc.getblock(block_hash, 2)["tx"]
    block_txids = set(tx["txid"] for tx in block_txs)
    txs_count = len(block_txids)

    # Ignore empty blocks.
    if txs_count == 1:
        continue

    child_count = 0
    parent_txids = set()  # To not double count parents.
    candidates_txids = set()  # Txs that would be considered for fee estimation.
    for tx in block_txs:
        is_child = False  # To not double count descendants.
        is_parent = False
        # Let's see if any of the input is a transaction mined in this block.
        for txin in tx["vin"]:
            if "txid" not in txin:
                continue  # Coinbase tx.
            # If it's in the list of txids for this block, it's a child of a CPFP.
            if txin["txid"] in block_txids:
                is_parent = True
                # Record the parent if it's new.
                if txin["txid"] not in parent_txids:
                    parent_txids.add(txin["txid"])
                # Record the child if it wasn't already.
                if not is_child:
                    is_child = True
                    child_count += 1
        if not is_child:
            candidates_txids.add(tx["txid"])

    # Update the totals.
    total_transactions += txs_count
    total_child_count += child_count
    parent_count = len(parent_txids)
    total_parent_count += parent_count
    candidate_count += len(candidates_txids)
    candidate_parent_count += len(parent_txids.intersection(candidates_txids))

    # Update the bounds.
    child_percentage = child_count / txs_count * 100
    if min_child_percentage is None or child_percentage < min_child_percentage:
        min_child_percentage = child_percentage
    if child_percentage > max_child_percentage:
        max_child_percentage = child_percentage
    parent_percentage = parent_count / txs_count * 100
    if min_parent_percentage is None or parent_percentage < min_parent_percentage:
        min_parent_percentage = parent_percentage
    if parent_percentage > max_parent_percentage:
        max_parent_percentage = parent_percentage

print(f"Between block heights {START_BLOCK_HEIGHT} and {STOP_BLOCK_HEIGHT}:")
print(f"    - The average percentage of transactions with a descendant in the same block is {total_parent_count / total_transactions * 100}%")
print(f"    - The average percentage of transactions with an ancestor in the same block is {total_child_count / total_transactions * 100}%")
print(f"    - The highest percentage of transactions with a descendant in the same block is {max_parent_percentage}%")
print(f"    - The highest percentage of transactions with an ancestor in the same block is {max_child_percentage}%")
assert all(perc is not None for perc in (min_parent_percentage, min_child_percentage))
print(f"    - The lowest percentage of transactions with a descendant in the same block is {min_parent_percentage}%")
print(f"    - The lowest percentage of transactions with an ancestor in the same block is {min_child_percentage}%")
print(f"    - The average percentage of transactions in a block that would be considered for fee estimation is {candidate_count / total_transactions * 100}%")
print(f"    - The average percentage of transactions with a descendant in the same block among candidates is {candidate_parent_count / candidate_count * 100}%")
