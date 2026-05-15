# Graph Report - data/graph_corpus/  (2026-05-14)

## Corpus Check
- Large corpus: 6 files · ~1,303,537 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 11 nodes · 8 edges · 3 communities (2 shown, 1 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Day 0 Cloud Onboarding|Day 0 Cloud Onboarding]]
- [[_COMMUNITY_Basic Switch Setup|Basic Switch Setup]]
- [[_COMMUNITY_Remote Management Interface|Remote Management Interface]]

## God Nodes (most connected - your core abstractions)
1. `Cisco DNA Center Cloud Onboarding` - 3 edges
2. `Obtaining IP Address` - 2 edges
3. `Create User Accounts` - 2 edges
4. `Setup Options (Wired Network)` - 2 edges
5. `Day 0 WebUI` - 1 edges
6. `Account Settings` - 1 edges
7. `DHCP Client Identifier` - 1 edges
8. `DHCP Client Configuration` - 1 edges
9. `Basic Device Settings` - 1 edges
10. `VTY Lines` - 1 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Communities (3 total, 1 thin omitted)

### Community 0 - "Day 0 Cloud Onboarding"
Cohesion: 0.4
Nodes (5): Basic Device Settings, Create User Accounts, DHCP Client Configuration, Obtaining IP Address, Setup Options (Wired Network)

### Community 1 - "Basic Switch Setup"
Cohesion: 0.5
Nodes (4): Account Settings, Cisco DNA Center Cloud Onboarding, Day 0 WebUI, DHCP Client Identifier

## Knowledge Gaps
- **7 isolated node(s):** `Day 0 WebUI`, `Account Settings`, `DHCP Client Identifier`, `DHCP Client Configuration`, `Basic Device Settings` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `Day 0 WebUI`, `Account Settings`, `DHCP Client Identifier` to the rest of the system?**
  _7 weakly-connected nodes found - possible documentation gaps or missing edges._