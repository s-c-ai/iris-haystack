# iris-haystack

<div align="center">

[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
[![Haystack 2.x](https://img.shields.io/badge/Haystack-2.x-orange)](https://haystack.deepset.ai/)

**A production-ready [Haystack 2.x](https://haystack.deepset.ai/) DocumentStore backed by [InterSystems IRIS](https://www.intersystems.com/products/intersystems-iris/).**

[Overview](#overview) • [Installation](#installation) • [Quick Start](#quick-start) • [Features](#features) • [Development](#development) • [Contributing](#contributing)

</div>

---

## Overview

`iris-haystack` integrates **InterSystems IRIS** as a `DocumentStore` for Haystack 2.x, enabling semantic vector search, keyword search, and metadata filtering — all using IRIS as the single data backend, with no additional infrastructure required.

Filters are evaluated using Haystack's official `document_matches_filter` utility, ensuring identical behavior to the `InMemoryDocumentStore` reference implementation and full compatibility with all Haystack filter mix-ins.

### Why IRIS?

InterSystems IRIS is a high-performance multimodel data platform widely used in healthcare, finance, and manufacturing. For AI applications it provides:

| Capability | Detail |
|---|---|
| `VECTOR(DOUBLE, N)` column type | Store embeddings natively in SQL, no separate vector database needed |
| `VECTOR_COSINE` SQL function | SIMD-optimized cosine similarity computed directly by the database engine |
| ANN index (HNSW) | Approximate nearest-neighbour search for large-scale collections |
| Standard SQL + JSON + globals | One platform for relational data, documents, and vectors |

---

## Features

| Method / Component | Description |
|---|---|
| `count_documents()` | Total number of documents in the store |
| `filter_documents(filters)` | Full Haystack filter protocol via `document_matches_filter` |
| `write_documents(docs, policy)` | INSERT with `TO_VECTOR(?, DOUBLE)` · FAIL / SKIP / OVERWRITE |
| `delete_documents(ids)` | DELETE by list of IDs · idempotent |
| `IRISEmbeddingRetriever` | Semantic search via native `VECTOR_COSINE` |
| `IRISBm25Retriever` | Keyword search via Okapi BM25 |
| Automatic reconnection | Exponential backoff · up to 3 retries (0.5 s, 1.0 s, 2.0 s) |
| Haystack `Secret` | Credentials via env vars · never hardcoded or serialized |
| `FilterPolicy` | `REPLACE` or `MERGE` for init-time and runtime filters |
| `to_dict` / `from_dict` | Full serialization for Haystack YAML / JSON pipelines |

---

## Installation


---

## Quick Start

```bash
# Set credentials as environment variables (recommended)
IRIS_CONNECTION_STRING="localhost:1972/USER"
IRIS_USERNAME="_system"
IRIS_PASSWORD="SYS"
```

```python
from haystack import Document
from haystack_integrations.document_stores.iris import IRISDocumentStore

store = IRISDocumentStore(embedding_dim=384)

store.write_documents([
    Document(content="IRIS is a multimodel database.", meta={"category": "db"}),
    Document(content="Haystack builds LLM pipelines.", meta={"category": "framework"}),
])

print(store.count_documents())
```

---

## Development

This project uses **Hatch** for project management and building.

To get started, clone the repository and ensure you have Hatch installed.


### Linting and Formatting

We use `ruff` to ensure code quality and formatting.
To automatically fix formatting issues, run:

```bash
hatch run fmt
```

To just check for issues without modifying the code:

```bash
hatch run fmt-check
```


### Testing

We use `pytest` for testing. Make sure your local InterSystems IRIS instance is running (via Docker) and your `.env` file is properly set up before running the tests.

To run the entire test suite:

```bash
hatch run test:all
```

To run tests with coverage reporting:

```bash
hatch run test:cov
```

(You can also run specifically `hatch run test:unit` or `hatch run test:integration`)

### Running Examples

To test the end-to-end RAG pipeline example:

```bash
hatch run example:run
```

### Build

To build the package for distribution (creating sdist and wheel):

```bash
hatch build
```

The generated files will be placed in the dist/ directory.


## Contributing

Contributions are welcome. Please open an issue or pull request.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Run the test suite: `pytest tests/ -v`
4. Open a pull request with a clear description of the change

---

## License

Apache 2.0 — see [LICENSE](LICENSE).

---

## References

- [Haystack 2.x — Custom DocumentStore](https://docs.haystack.deepset.ai/docs/creating-custom-document-stores)
- [Haystack — Metadata Filtering](https://docs.haystack.deepset.ai/docs/metadata-filtering)
- [InterSystems IRIS — Vector Search](https://docs.intersystems.com/irislatest/csp/docbook/DocBook.UI.Page.cls?KEY=GSQL_vecsearch)
- [intersystems-irispython — DB-API driver](https://pypi.org/project/intersystems-irispython/)
- [InterSystems Developer Community](https://community.intersystems.com/)
- [Haystack Integrations](https://haystack.deepset.ai/integrations)