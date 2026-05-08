# Graph Report - temp_graph_src  (2026-05-08)

## Corpus Check
- 3 files · ~217,043 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 14 nodes · 8 edges · 6 communities (4 shown, 2 thin omitted)
- Extraction: 75% EXTRACTED · 25% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Junos OSPF Monitoring|Junos OSPF Monitoring]]
- [[_COMMUNITY_OSPF Hierarchy & Roles|OSPF Hierarchy & Roles]]
- [[_COMMUNITY_OSPF SPF & LSA Analysis|OSPF SPF & LSA Analysis]]
- [[_COMMUNITY_Vendor Config Modes|Vendor Config Modes]]
- [[_COMMUNITY_Cisco 9300 Guide|Cisco 9300 Guide]]
- [[_COMMUNITY_Junos CLI Guide|Junos CLI Guide]]

## God Nodes (most connected - your core abstractions)
1. `Open Shortest Path First (OSPF)` - 2 edges
2. `OSPF Interface` - 2 edges
3. `Link-State Advertisement (LSA)` - 2 edges
4. `Junos Configuration Mode` - 2 edges
5. `Verifying and Monitoring OSPF` - 1 edges
6. `OSPF Neighbor` - 1 edges
7. `OSPF Area` - 1 edges
8. `Designated Router (DR)` - 1 edges
9. `Shortest Path First (SPF) Algorithm` - 1 edges
10. `Cisco Global Configuration Mode` - 1 edges

## Surprising Connections (you probably didn't know these)
- `Cisco Global Configuration Mode` --related_to--> `Junos Configuration Mode`  [INFERRED]
  temp_graph_src/catalyst_9300_config_guide_17_6.txt → temp_graph_src/junos-cli.txt
- `Junos Traceoptions` --related_to--> `Link-State Advertisement (LSA)`  [EXTRACTED]
  temp_graph_src/junos-cli.txt → temp_graph_src/junos-ospf.txt

## Hyperedges (group relationships)
- **OSPF Verification and Monitoring** — net_ospf_neighbor, net_ospf_interface, net_ospf_dr, net_ospf_lsa [INFERRED 0.80]

## Communities (6 total, 2 thin omitted)

### Community 0 - "Junos OSPF Monitoring"
Cohesion: 0.67
Nodes (3): Verifying and Monitoring OSPF, Open Shortest Path First (OSPF), OSPF Neighbor

### Community 1 - "OSPF Hierarchy & Roles"
Cohesion: 0.67
Nodes (3): OSPF Area, Designated Router (DR), OSPF Interface

### Community 2 - "OSPF SPF & LSA Analysis"
Cohesion: 0.67
Nodes (3): Junos Traceoptions, Link-State Advertisement (LSA), Shortest Path First (SPF) Algorithm

### Community 3 - "Vendor Config Modes"
Cohesion: 0.67
Nodes (3): Cisco Global Configuration Mode, Junos Commit Command, Junos Configuration Mode

## Knowledge Gaps
- **10 isolated node(s):** `Cisco Catalyst 9300 Configuration Guide`, `Junos CLI Reference`, `Verifying and Monitoring OSPF`, `OSPF Neighbor`, `OSPF Area` (+5 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `Cisco Catalyst 9300 Configuration Guide`, `Junos CLI Reference`, `Verifying and Monitoring OSPF` to the rest of the system?**
  _10 weakly-connected nodes found - possible documentation gaps or missing edges._