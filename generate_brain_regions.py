#!/usr/bin/env python3
"""
Generate brain_regions.json for the 9-category-group segmentation.

Reads the existing brain_regions.json (1982 nodes, 5630 edges) and
redistributes nodes across 9 regions matching the category groups in
backend/profile_scoring/categories.py:

  Fundamentals (4 cats)    │  OOP (9 cats)            │  Data Structures (8 cats)
  Algorithms (6 cats)      │  Systems (8 cats)        │  Frontend (5 cats)
  Dev Practices (5 cats)   │  Product (3 cats)        │  Hackathon (3 cats)

Nodes are assigned to regions based on spatial proximity to 9 pre-chosen
centre positions arranged around a brain shape.  Edges are preserved
exactly as-is; inter-region paths are recomputed.

Usage:
    python generate_brain_regions.py
"""

import json, math, sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "frontend" / "public" / "brain_regions.json"
DST = SRC  # overwrite in place


# ── 9 new regions (order = index) ──────────────────────────────────
REGIONS = [
    # id                      label               color        target centre (x, y, z)
    ("Region_Fundamentals",   "Fundamentals",      "#60a5fa",  (-0.42,  0.38,  0.00)),
    ("Region_OOP",            "OOP",               "#a78bfa",  ( 0.42,  0.38,  0.00)),
    ("Region_DataStructures", "Data Structures",   "#34d399",  (-0.38,  0.00,  0.42)),
    ("Region_Algorithms",     "Algorithms",        "#fbbf24",  ( 0.38,  0.00,  0.42)),
    ("Region_Systems",        "Systems",           "#f472b6",  ( 0.00,  0.00, -0.48)),
    ("Region_Frontend",       "Frontend",          "#fb923c",  (-0.38,  0.00, -0.42)),
    ("Region_DevPractices",   "Dev Practices",     "#2dd4bf",  ( 0.38,  0.00, -0.42)),
    ("Region_Product",        "Product",           "#e879f9",  (-0.20, -0.50,  0.20)),
    ("Region_Hackathon",      "Hackathon",         "#f87171",  ( 0.20, -0.50,  0.20)),
]

# Target node-count proportions (based on category counts)
# Fundamentals:4  OOP:9  DS:8  Algo:6  Sys:8  FE:5  DevP:5  Prod:3  Hack:3
WEIGHTS = [4, 9, 8, 6, 8, 5, 5, 3, 3]
TOTAL_W = sum(WEIGHTS)


def dist(a, b):
    return math.sqrt(sum((ai - bi) ** 2 for ai, bi in zip(a, b)))


def generate():
    # Load existing data
    with open(SRC) as f:
        data = json.load(f)

    nodes = data["nodes"]
    edges = data["edges"]
    total_nodes = len(nodes)

    print(f"Loaded {total_nodes} nodes, {len(edges)} edges from existing file")

    centres = [r[3] for r in REGIONS]

    # ── Assign each node to the nearest region centre ──────────
    # But we also want to respect the weight proportions roughly.
    # Strategy: compute distance to each centre, then do a weighted
    # assignment with a soft quota system.

    # First pass: for each node, rank regions by distance
    node_rankings = []
    for node in nodes:
        pos = node["position"]
        dists = [(i, dist(pos, centres[i])) for i in range(len(REGIONS))]
        dists.sort(key=lambda x: x[1])
        node_rankings.append(dists)

    # Target counts
    targets = [round(w / TOTAL_W * total_nodes) for w in WEIGHTS]
    # Adjust rounding error
    diff = total_nodes - sum(targets)
    # Add/remove from largest region
    targets[1] += diff  # OOP is largest

    # Greedy assignment: process nodes sorted by how "clear" their
    # best assignment is (smallest gap between 1st and 2nd choice)
    assignments = [None] * total_nodes
    counts = [0] * len(REGIONS)

    # Build priority: nodes with the smallest dist to their best centre first
    node_order = sorted(range(total_nodes), key=lambda i: node_rankings[i][0][1])

    for ni in node_order:
        rankings = node_rankings[ni]
        assigned = False
        for region_idx, _ in rankings:
            if counts[region_idx] < targets[region_idx]:
                assignments[ni] = region_idx
                counts[region_idx] += 1
                assigned = True
                break
        if not assigned:
            # All targets full — assign to nearest regardless
            assignments[ni] = rankings[0][0]
            counts[rankings[0][0]] += 1

    # ── Build new node list ────────────────────────────────────
    for node in nodes:
        node["region"] = assignments[node["id"]]

    # ── Compute region metadata ────────────────────────────────
    region_node_ids = [[] for _ in REGIONS]
    for node in nodes:
        region_node_ids[node["region"]].append(node["id"])

    new_regions = []
    for i, (rid, label, color, _target_centre) in enumerate(REGIONS):
        nids = region_node_ids[i]
        if nids:
            cx = sum(nodes[n]["position"][0] for n in nids) / len(nids)
            cy = sum(nodes[n]["position"][1] for n in nids) / len(nids)
            cz = sum(nodes[n]["position"][2] for n in nids) / len(nids)
            centre = [round(cx, 4), round(cy, 4), round(cz, 4)]
        else:
            centre = list(_target_centre)

        new_regions.append({
            "id": rid,
            "label": label,
            "color": color,
            "nodeCount": len(nids),
            "nodeIds": sorted(nids),
            "center": centre,
        })

    # ── Recompute inter-region edges ───────────────────────────
    inter_region = []
    for edge in edges:
        a, b = edge
        if nodes[a]["region"] != nodes[b]["region"]:
            inter_region.append(edge)

    # ── Assemble output ────────────────────────────────────────
    output = {
        "meta": {
            "totalNodes": total_nodes,
            "totalEdges": len(edges),
            "interRegionEdges": len(inter_region),
            "regionCount": len(REGIONS),
            "scale": 1,
            "description": "9-segment brain mesh — one segment per category group",
        },
        "regions": new_regions,
        "nodes": nodes,
        "edges": edges,
        "interRegionPaths": inter_region,
    }

    with open(DST, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"\nWrote {DST}")
    print(f"  Regions: {len(new_regions)}")
    for r in new_regions:
        print(f"    {r['id']:25s}  {r['nodeCount']:4d} nodes  centre={r['center']}")
    print(f"  Edges:              {len(edges)}")
    print(f"  Inter-region edges: {len(inter_region)}")


if __name__ == "__main__":
    generate()
