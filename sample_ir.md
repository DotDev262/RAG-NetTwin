"Enable OSPF process 10 on Router-A (Cisco IOS-XE 17.6) for interface Gig0/1 with IP 192.168.1.1/24, ensuring no downtime."


```json
    1 {

    2   "intent_id": null,

    3   "protocol": "OSPF",

    4   "action": "enable",

    5   "devices": [

    6     {

    7       "name": "Router-A",

    8       "vendor": "cisco",

    9       "os_type": "ios-xe",

   10       "os_version": "17.6"

   11     }

   12   ],

   13   "parameters": {

   14     "process_id": "10",

   15     "interface": "Gig0/1",

   16     "ip": "192.168.1.1/24"

   17   },

   18   "requirements": ["no_downtime"]

   19 } 
````

---

# ChromaDB Knowledge Storage Model

The project utilizes a "Metadata-Anchored Knowledge Model" to ensure deterministic, version-specific grounding during retrieval.

```text
+----------------------------------------------------------------------------------+
|                          CHROMADB COLLECTION: "network_docs"                     |
+----------------------------------------------------------------------------------+
|                                                                                  |
|  RECORD ID: "chunk_000452"                                                       |
|  +----------------------------------------------------------------------------+  |
|  | [ 1. VECTOR EMBEDDING ] (The "Semantic DNA")                               |  |
|  | [0.12, -0.45, 0.88, 0.03, -0.21, ... 384 dimensions]                       |  |
|  +-----------------------^----------------------------------------------------+  |
|                          | (Generated via all-MiniLM-L6-v2)                      |
|                          |                                                       |
|  +-----------------------v----------------------------------------------------+  |
|  | [ 2. DOCUMENT TEXT ] (The "Knowledge Content")                            |  |
|  | "router ospf 10                                                            |  |
|  |  area 0 range 192.168.1.0 255.255.255.0"                                   |  |
|  +----------------------------------------------------------------------------+  |
|                                                                                  |
|  +----------------------------------------------------------------------------+  |
|  | [ 3. METADATA ANCHORS ] (The "Deterministic Filters")                      |  |
|  | {                                                                          |  |
|  |   "vendor":     "cisco",            <-- Hard constraint for Vendor         |  |
|  |   "os_version": "ios-xe-17.6",      <-- Hard constraint for Version Lock   |  |
|  |   "tier":       1,                  <-- Validation level (Batfish/GNS3)    |  |
|  |   "hierarchy":  "['OSPF', 'Area']", <-- Structural context                 |  |
|  |   "source":     "cat9300_cfg.pdf"   <-- Lineage/Traceability               |  |
|  | }                                                                          |  |
|  +----------------------------------------------------------------------------+  |
|                                                                                  |
+----------------------------------------------------------------------------------+
```

### Storage Principles:

1.  **Deterministic Grounding (Version Lock)**:
    Metadata filters (e.g., `os_version`) are applied during the query phase to physically ignore non-matching documentation, preventing cross-version hallucinations.

2.  **Semantic Retrieval**:
    Vector embeddings allow for matching intents to documentation based on meaning rather than just keywords.

3.  **Traceable Synthesis**:
    Source file names and chunk IDs are preserved in metadata, allowing the system to cite its references directly in the generated CLI output.

---

# How the System Queries ChromaDB

The retrieval process follows a **"Filtered-Semantic-Search"** workflow to ensure precision:

### 1. Hard Metadata Filtering (Deterministic)
Before searching for meaning, the system applies a **Metadata Filter**. If the intent specifies `Cisco IOS-XE 17.6`, the query engine tells ChromaDB: *"Only look at records where `os_version` is exactly `ios-xe-17.6`."* This instantly eliminates irrelevant data from Juniper or other Cisco versions.

### 2. Semantic Similarity Search (Vector)
Once the data is filtered, the system performs a **Vector Search**. It compares the mathematical "embedding" of your intent (e.g., *"Set up OSPF"*) against the filtered document chunks. It calculates the **Cosine Distance** to find the top-K chunks that are most similar in meaning.

### 3. Context Assembly
The top retrieved chunks (e.g., the top 5 most relevant command snippets) are then formatted into a single context block. This block is injected into the LLM prompt, acting as the "source of truth" for configuration synthesis.

**Example Query Logic:**
```python
results = collection.query(
    query_texts=["OSPF create area 0"],  # Semantic search string
    n_results=5,                        # Get top 5 most relevant hits
    where={"os_version": "ios-xe-17.6"} # CRITICAL: Version Lock filter
)
```
