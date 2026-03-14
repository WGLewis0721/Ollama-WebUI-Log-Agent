# Agent Module Reference

This document describes every Python file in the `agent/` directory — what it does, how it fits into the overall system, the key classes and functions it exposes, and how it is configured.

---

## Table of Contents

| File | Role |
|---|---|
| [api_server.py](#api_serverpy) | FastAPI entry-point — routes analyst queries |
| [main_rag.py](#main_ragpy) | RAG pipeline — fetch, enrich, analyse, save |
| [main_opensearch.py](#main_opensearchpy) | Earlier OpenSearch-enabled agent (standalone) |
| [main.py](#mainpy) | Original file-based log analyst agent |
| [query_generator.py](#query_generatorpy) | Natural language → OpenSearch DSL |
| [opensearch_executor.py](#opensearch_executorpy) | Execute DSL queries, format results |
| [opensearch_integration.py](#opensearch_integrationpy) | AWS OpenSearch client wrapper |
| [rag_module.py](#rag_modulepy) | k-NN embeddings and vector search |
| [rag_indexer.py](#rag_indexerpy) | Index S3 runbooks into OpenSearch |
| [document_indexer.py](#document_indexerpy) | High-level S3 → OpenSearch indexing pipeline |
| [s3_document_fetcher.py](#s3_document_fetcherpy) | Read and write documents in S3 |
| [dashboard.py](#dashboardpy) | Flask web dashboard (port 5000) |

---

## api_server.py

**Role:** FastAPI application — the primary entry-point for all analyst requests arriving from OpenWebUI.

### Overview

`api_server.py` exposes an OpenAI-compatible REST API on port **7000**. When a message arrives it inspects the query text and routes it to one of two modes:

| Mode | Trigger | What happens |
|---|---|---|
| **Query mode** | Specific factual question (e.g. "What are the top 5 source IPs?") | `query_generator` converts the question to DSL → `opensearch_executor` runs it → LLM explains the real results |
| **Report mode** | Generic analysis request (e.g. "Give me a SOC summary") | `main_rag.fetch_logs` fetches a broad log sample → RAG retrieves runbook context → LLM writes a structured SOC report |

The routing decision is made by `query_generator.is_specific_question()`.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/models` | Returns the model manifest in OpenAI list format |
| `POST` | `/v1/chat/completions` | Main analyst endpoint — accepts OpenAI `messages` payload |
| `GET` | `/health` | Liveness check — returns `{"status": "ok"}` |
| `GET` | `/v1/latest_query` | Returns the most recent query-mode result (for dashboard polling) |

### Key Functions

#### `explain_results(user_question, formatted_results, rag_context="")`
Sends OpenSearch query results to `llama3.1:8b` for plain-language explanation. Returns a concise analyst-facing answer.

#### `build_openai_response(content, model, metadata)`
Wraps a string response in the OpenAI `chat.completion` envelope expected by OpenWebUI.

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `OPENSEARCH_INDEX` | `cwl-*,appgate-logs-*,security-logs-*` | Index patterns to search |
| `TIME_RANGE_MINUTES` | `99999` | How far back to fetch logs in report mode |
| `MODEL_NAME` | `llama3.1:8b` | LLM used for explanation and reporting |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama inference endpoint |
| `OUTPUT_DIR` | `/app/output` | Where to persist the latest query payload |

### Dependencies

Imports from: `main_rag`, `query_generator`, `opensearch_executor`

---

## main_rag.py

**Role:** Core RAG pipeline — wires together the OpenSearch client, RAG retrieval, LLM analysis, and report saving into a single reusable set of functions called by `api_server.py`.

### Overview

`main_rag.py` is not a standalone service; it is a library module imported by `api_server.py`. It also has a `main()` entry-point for running scheduled analysis cycles independently (e.g. via a cron job or watch-mode loop).

The analysis pipeline is:

```
fetch_logs() → retrieve_rag_context() → analyze_logs() → save_report()
```

### Key Functions

#### `get_opensearch_client()`
Returns a cached `OpenSearchLogFetcher` instance. Initialises the client on first call using container IAM credentials. Subsequent calls return the cached object.

#### `fetch_logs(client, index_pattern=None, time_range_minutes=None)`
Iterates over every comma-separated index pattern in `OPENSEARCH_INDEX`, calls `client.fetch_logs()` for each, normalises every document via `_normalize()`, and returns the combined list.

#### `_normalize(src, index)`
Maps a raw OpenSearch `_source` dict into a consistent four-field structure (`timestamp`, `index`, `type`, `message`/`raw`) based on the index name:

| Index contains | Normalised type | Key fields extracted |
|---|---|---|
| `cwl-` | `palo_alto` | `src_ip`, `dst_ip`, `rule`, `action` from CSV message |
| `appgate` | `appgate` | `message`, `hostname`, `level`, `src_ip`, `action` |
| `security` | `security` | `message`, `device_type`, `log_type` |
| *(other)* | `generic` | `message` |

#### `retrieve_rag_context(client, logs)`
Builds a sample query from the first 30 log messages, calls `rag_module.RAGManager.search_similar()` to retrieve relevant runbook chunks from the `knowledge-base` index, and returns formatted context text for inclusion in the LLM prompt.

Returns an empty string when RAG is disabled (`ENABLE_RAG=false`) or no matching chunks are found.

#### `analyze_logs(logs, rag_context="", user_query="")`
Pre-computes factual summaries from the log list (timestamps, top IPs, firewall rules, actions, correlated IPs) to prevent the model from hallucinating counts or addresses. Sends this context plus the user query to `llama3.1:8b` via the Ollama `/api/chat` endpoint.

Two prompt paths:
- **User query provided:** Instructs the model to answer the specific question using only the provided data.
- **No query:** Requests a structured 9-section SOC report (Executive Summary through Recommendations).

#### `save_report(analysis, logs, rag_context)`
Persists the analysis as both a JSON file and a plain-text file in `OUTPUT_DIR`. Returns the base `Path` of the saved files (without extension).

#### `run_cycle()`
Executes one complete fetch → RAG → analyse → save cycle. Called by `main()` in watch mode or when `--once` is passed.

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `OPENSEARCH_ENDPOINT` | *(required)* | AWS OpenSearch domain hostname |
| `AWS_REGION` | `us-gov-west-1` | AWS region for SigV4 signing |
| `OPENSEARCH_INDEX` | `cwl-*,appgate-logs-*,security-logs-*` | Comma-separated index patterns |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama inference endpoint |
| `MODEL_NAME` | `llama3.1:8b` | LLM for analysis |
| `ENABLE_RAG` | `true` | Toggle RAG context retrieval |
| `RAG_K` | `3` | Number of RAG chunks to retrieve |
| `RAG_INDEX` | `knowledge-base` | OpenSearch index holding runbook embeddings |
| `TIME_RANGE_MINUTES` | `64800` | Log fetch window (45 days) |
| `WATCH_MODE` | `true` | Run in continuous loop when `true` |
| `WATCH_INTERVAL_MINUTES` | `30` | Sleep duration between cycles in watch mode |
| `OUTPUT_DIR` | `/app/output` | Report output directory |

---

## main_opensearch.py

**Role:** Standalone OpenSearch-enabled agent — an earlier iteration before the codebase was split into the current modular architecture.

### Overview

`main_opensearch.py` contains a self-contained `LogAnalystAgent` class that can optionally connect to OpenSearch for log fetching while retaining the file-based analysis path. It is **not imported** by `api_server.py`; the production stack uses `main_rag.py` instead.

### Class: `LogAnalystAgent`

| Method | Description |
|---|---|
| `__init__(ollama_url, model_name, output_dir, opensearch_endpoint, aws_region)` | Initialises the Ollama client and, if `opensearch_endpoint` is provided, an `OpenSearchLogFetcher` |
| `ensure_model()` | Checks that the configured model exists in Ollama, pulling it if necessary |
| `fetch_logs_from_opensearch(index_pattern, time_range_minutes, application, errors_only)` | Fetches logs from OpenSearch and returns `(log_content_str, stats_dict)` |
| `analyze_logs(log_content, analysis_type, metadata)` | Sends log text to Ollama and returns a structured analysis dict |
| `_create_analysis_prompt(log_content, analysis_type, metadata)` | Builds a context-aware prompt for `general`, `security`, `performance`, or `errors` analysis |
| `save_analysis(analysis, source_name)` | Saves the analysis as both `.json` and `.txt` files in `output_dir` |

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `MODEL_NAME` | `llama3.1:8b` | LLM for analysis |
| `OUTPUT_DIR` | `/app/output` | Report output directory |
| `ANALYSIS_TYPE` | `general` | `general`, `security`, `performance`, or `errors` |
| `OPENSEARCH_ENDPOINT` | *(optional)* | If set, logs are fetched from OpenSearch |
| `AWS_REGION` | `us-east-1` | AWS region |
| `OPENSEARCH_INDEX` | `logs-*` | Index pattern |
| `TIME_RANGE_MINUTES` | `60` | Log fetch window |
| `APPLICATION_NAME` | *(optional)* | Filter logs to a single application |
| `ERRORS_ONLY` | `false` | When `true`, fetches only ERROR/CRITICAL logs |
| `WATCH_MODE` | `false` | Continuous monitoring loop |
| `WATCH_INTERVAL_MINUTES` | `5` | Sleep between analysis cycles in watch mode |

---

## main.py

**Role:** Original file-based log analyst — reads `.log` files from a local directory, extracts patterns, and generates LLM analysis reports.

### Overview

`main.py` is the earliest version of the agent. It has no OpenSearch or RAG dependency and is used with the basic `docker-compose.yml` stack. Place `.log` files in the configured `LOG_DIR` and the agent will process them.

### Class: `LogAnalystAgent`

| Method | Description |
|---|---|
| `__init__(ollama_url, model_name, output_dir)` | Initialises the Ollama client |
| `ensure_model()` | Ensures the LLM is available, pulling it if necessary |
| `read_log_file(log_path, max_lines=1000)` | Reads a log file, truncating to the last `max_lines` lines if necessary |
| `extract_log_patterns(log_content)` | Counts errors, warnings, exceptions, critical events, and HTTP 4xx/5xx codes using regex |
| `analyze_logs(log_content, analysis_type="general")` | Sends log content and extracted pattern counts to Ollama, returns an analysis dict |
| `_create_analysis_prompt(log_content, patterns, analysis_type)` | Builds the LLM prompt, including extracted statistics and a focus instruction per analysis type |
| `save_analysis(analysis, log_filename)` | Saves the analysis as `.json` and a human-readable `.txt` report |
| `analyze_directory(log_dir, pattern="*.log", analysis_type="general")` | Iterates over matching files in a directory, analyses each, and writes a `summary_*.json` |

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `MODEL_NAME` | `llama3.2:3b` | LLM for analysis |
| `LOG_DIR` | `/app/logs` | Directory containing `.log` files to analyse |
| `OUTPUT_DIR` | `/app/output` | Where to write analysis reports |
| `ANALYSIS_TYPE` | `general` | `general`, `security`, `performance`, or `errors` |
| `WATCH_MODE` | `false` | Re-analyse every 5 minutes when `true` |

---

## query_generator.py

**Role:** Converts natural-language analyst questions into valid OpenSearch DSL JSON using `llama3.2:3b` at temperature 0.

### Overview

`query_generator.py` is called by `api_server.py` in **query mode** to produce the DSL body that is then executed by `opensearch_executor.run_query()`. It uses a highly constrained system prompt that includes real field names, known data characteristics, and worked examples to maximise determinism.

If the LLM returns malformed JSON or the request times out, `_fallback_query()` provides a safe keyword-matched fallback.

### Key Functions

#### `generate_opensearch_query(user_question)`
Sends the user's question to `llama3.2:3b` with a strict system prompt instructing it to return only raw JSON. Strips any Markdown code fences from the response, extracts the first JSON object, and returns it as a Python dict.

**Returns:** A valid OpenSearch query dict, or a safe fallback dict if generation fails.

#### `_fallback_query(question)`
Performs simple keyword matching on the question to return one of three canned queries:
- `deny`/`block` keywords → filter by action `deny`
- `top ip`/`source ip` keywords → terms aggregation on `src_ip.keyword`
- `recent`/`latest` keywords → 20 most recent documents

Falls back to the most recent 50 documents when no keyword matches.

#### `is_specific_question(user_query)`
Heuristic classifier that determines whether a query should be handled as **query mode** (returns `True`) or **report mode** (returns `False`).

Logic:
1. Short queries (< 10 chars) → report mode
2. Contains a generic-report trigger phrase (`analyze`, `summarize`, `overview`, etc.) → report mode
3. Contains a question signal word (`which`, `top`, `how many`, `list`, etc.) → query mode
4. Long queries (> 30 chars) with no generic trigger → query mode

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama inference endpoint |
| `QUERY_MODEL` | `llama3.2:3b` | Model for DSL generation (use a small, fast model) |
| `OPENSEARCH_INDEX` | `cwl-*,appgate-logs-*,security-logs-*` | Injected into the system prompt for context |

---

## opensearch_executor.py

**Role:** Execute an LLM-generated OpenSearch query and format the results into a string the LLM can understand.

### Overview

`opensearch_executor.py` is a thin execution and formatting layer called by `api_server.py` in query mode. It accepts the raw query dict produced by `query_generator.py`, runs it against OpenSearch, and converts the response into a compact readable form suitable for sending to `llama3.1:8b` for explanation.

### Key Functions

#### `run_query(client, query, index=None)`
Executes an OpenSearch query against the configured index pattern.

- Unwraps the underlying `opensearchpy.OpenSearch` client if the `client` argument is an `OpenSearchLogFetcher` wrapper.
- Accepts both `dict` and JSON string queries.
- Automatically rewrites `_doc_count` → `_count` in aggregation order clauses to fix a common LLM generation mistake.
- Returns the raw OpenSearch response dict, or a safe error envelope on failure.

#### `format_results_for_llm(query_result, max_hits=15)`
Converts a raw OpenSearch response into a compact, LLM-readable text block:

- Reports the total matching document count.
- For **aggregation results**: lists each bucket with its key and `doc_count`.
- For **hit results**: formats up to `max_hits` entries with index, timestamp, source IP, destination IP, rule name, action, and message fields.

#### `summarize_for_dashboard(user_question, generated_query, query_result, explanation)`
Builds the JSON payload written to `output/latest_query.json`. Contains everything an analyst needs to audit and reproduce the query:
- Original user question
- Generated DSL query
- Hit count and aggregation results
- Up to 25 sample `_source` documents
- LLM explanation
- A `reproduce_with` block showing the exact `POST /<index>/_search` call

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `OPENSEARCH_INDEX` | `cwl-*,appgate-logs-*,security-logs-*` | Default target index for `run_query()` |

---

## opensearch_integration.py

**Role:** AWS OpenSearch client wrapper — authenticates via AWS SigV4 IAM and provides typed methods for fetching and formatting logs.

### Overview

`opensearch_integration.py` provides the `OpenSearchLogFetcher` class used throughout the codebase. It handles all connection and authentication details, exposing a clean interface for fetching logs by time range, application, log level, or arbitrary text pattern.

### Class: `OpenSearchLogFetcher`

| Method | Description |
|---|---|
| `__init__(opensearch_endpoint, region, use_aws_auth, username, password)` | Connects to OpenSearch using AWS IAM SigV4 (default) or basic auth |
| `fetch_logs(index_pattern, time_range_minutes, max_logs, query, log_level_filter)` | General-purpose log fetch with optional custom query and level filter |
| `fetch_logs_by_application(application_name, time_range_minutes, max_logs)` | Fetches logs matching a specific `kubernetes.labels.app` value |
| `fetch_error_logs(index_pattern, time_range_minutes, max_logs)` | Convenience wrapper — fetches only ERROR, CRITICAL, and FATAL logs |
| `format_logs_for_analysis(logs)` | Converts raw log dicts into human-readable timestamped lines for LLM input |
| `get_log_statistics(logs)` | Computes counts by log level and service, plus the time range covered |
| `search_by_pattern(pattern, index_pattern, time_range_minutes, max_logs)` | Full-text search using `query_string` on the `message` field |

### Authentication

When `use_aws_auth=True` (default), the client uses `boto3.Session().get_credentials()` with `requests_aws4auth.AWS4Auth` to sign requests. This picks up credentials from the EC2 instance IAM role, environment variables, or `~/.aws/credentials` in that order.

Basic username/password authentication is also supported by passing `use_aws_auth=False` together with `username` and `password`.

---

## rag_module.py

**Role:** Retrieval-Augmented Generation document management — chunk, embed, index, and search runbook documents in OpenSearch using k-NN vector search.

### Overview

`rag_module.py` provides two classes:

- **`RAGManager`** handles all interactions with the OpenSearch `knowledge-base` index: creating the k-NN index, generating embeddings using `nomic-embed-text` via Ollama, indexing chunked documents, and performing vector similarity search.
- **`RAGEnhancedAnalyzer`** wraps `RAGManager` to add a full analysis flow: search for relevant context, build a context-augmented prompt, and return an LLM analysis dict.

### Class: `RAGManager`

| Method | Description |
|---|---|
| `__init__(opensearch_endpoint, ollama_url, embedding_model, region, index_name)` | Initialises AWS-authenticated OpenSearch client and Ollama client |
| `ensure_embedding_model()` | Checks that the embedding model is available in Ollama, pulling it if necessary |
| `create_index(dimension=768)` | Creates an OpenSearch k-NN index with HNSW (`cosinesimil`, `nmslib`) if it does not already exist |
| `chunk_text(text, chunk_size=500, overlap=50)` | Splits text into overlapping chunks, preferring sentence or newline boundaries |
| `generate_embedding(text)` | Calls Ollama `/api/embeddings` and returns the embedding vector |
| `index_document(text, source, metadata, chunk_size=500)` | Chunks a document, generates an embedding for each chunk, and indexes all chunks into OpenSearch. Returns the number of chunks indexed |
| `search_similar(query, k=5, min_score=0.5)` | Embeds the query and runs a k-NN search. Returns documents with their text, source, and similarity score |
| `get_document_count()` | Returns the total number of indexed chunks |
| `delete_document(source)` | Deletes all chunks associated with a given source identifier |

### Class: `RAGEnhancedAnalyzer`

| Method | Description |
|---|---|
| `__init__(rag_manager, ollama_client)` | Accepts an initialised `RAGManager` and Ollama client |
| `analyze_with_context(log_content, model, k=3)` | Searches for relevant runbook context, builds an augmented prompt, and returns an LLM analysis dict including which sources were used |
| `_extract_search_query(log_content)` | Extracts the first few ERROR/CRITICAL lines (or the first 10 lines) as the RAG search query |
| `_build_context_section(context_docs)` | Formats retrieved chunks into a numbered **Relevant Documentation** block |

### Index Schema

| Field | Type | Description |
|---|---|---|
| `text` | `text` | Chunk content |
| `embedding` | `knn_vector` (768-dim) | `nomic-embed-text` vector |
| `source` | `keyword` | Source identifier (S3 key or filename) |
| `chunk_id` | `keyword` | MD5 hash of `{source}_{chunk_index}` |
| `chunk_index` | integer | Position of chunk within the document |
| `metadata` | `object` | Arbitrary metadata (size, extension, etc.) |
| `timestamp` | `date` | Indexing time |

---

## rag_indexer.py

**Role:** CLI tool to populate the `knowledge-base` OpenSearch index from an S3 bucket using word-based chunking and `nomic-embed-text` embeddings.

### Overview

`rag_indexer.py` is a leaner, production-focused alternative to `document_indexer.py`. It downloads documents directly from S3 using `boto3`, chunks them by word count with configurable overlap, generates embeddings via the Ollama REST API, and uses OpenSearch bulk indexing for efficiency. Duplicate detection is performed by comparing a content MD5 hash (`doc_id`).

### Key Functions

#### `get_client()`
Creates and returns an `opensearchpy.OpenSearch` client authenticated with AWS SigV4.

#### `get_embedding(text)`
Posts to `{OLLAMA_URL}/api/embeddings` with a 2000-character text limit. Returns an empty list on failure.

#### `chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)`
Splits text by whitespace into overlapping word-count windows. Default: 400 words per chunk with 80-word overlap.

#### `index_documents(client)`
Main indexing loop:
1. Lists all S3 objects under `S3_PREFIX` matching supported extensions (`.txt`, `.md`, `.json`, `.log`, `.yaml`, `.yml`).
2. Skips files already indexed (matched by `doc_id`).
3. Chunks each document, generates embeddings, and bulk-indexes all chunks.

Returns `(total_docs, total_chunks)`.

#### `show_stats(client)`
Prints the total chunk count and per-document breakdown from the `knowledge-base` index.

#### `test_search(client, query)`
Generates an embedding for `query` and runs a k-NN search, printing the top 3 results.

### CLI Usage

```bash
python rag_indexer.py index    # Download from S3 and index (default)
python rag_indexer.py stats    # Show index statistics
python rag_indexer.py test <query>  # Test k-NN search
python rag_indexer.py clear    # Delete all documents (prompts for confirmation)
```

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `S3_BUCKET_NAME` | `cnap-dev-il6-ollama-knowledge-base-wgl` | Source S3 bucket |
| `S3_PREFIX` | `knowledge/base` | Key prefix within the bucket |
| `OPENSEARCH_ENDPOINT` | *(required)* | OpenSearch domain hostname |
| `AWS_REGION` | `us-gov-west-1` | AWS region |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama endpoint |

---

## document_indexer.py

**Role:** High-level document indexing pipeline — orchestrates `S3DocumentFetcher` and `RAGManager` to index all runbooks from S3 into the OpenSearch knowledge base.

### Overview

`document_indexer.py` provides the `DocumentIndexer` class, which composes `s3_document_fetcher.S3DocumentFetcher` for S3 access and `rag_module.RAGManager` for embedding and indexing. It is designed for one-off or bootstrapping use and adds `colorama`-coloured console output.

For ongoing automated re-indexing in the production stack, `rag_indexer.py` is preferred.

### Class: `DocumentIndexer`

| Method | Description |
|---|---|
| `__init__(s3_bucket, s3_prefix, opensearch_endpoint, ollama_url, aws_region)` | Creates `S3DocumentFetcher` and `RAGManager` instances |
| `setup()` | Ensures the embedding model is available and creates the k-NN index |
| `index_all_documents(extensions, force_reindex)` | Lists documents for each extension, reads content from S3, and indexes each via `RAGManager.index_document()`. Returns total chunks indexed |
| `index_single_document(s3_key)` | Reads and indexes a single S3 object |
| `reindex_document(s3_key)` | Deletes existing chunks for an S3 key and re-indexes the document |
| `get_stats()` | Returns `{"total_chunks": int, "index_name": str}` |
| `test_search(query, k=3)` | Runs a similarity search and prints formatted results |

### CLI Usage

```bash
python document_indexer.py index_all         # Index all supported documents from S3
python document_indexer.py stats             # Print indexing statistics
python document_indexer.py test <query>      # Run a test similarity search
```

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `S3_BUCKET_NAME` | *(required)* | Source S3 bucket |
| `S3_PREFIX` | `knowledge-base/` | Key prefix within the bucket |
| `OPENSEARCH_ENDPOINT` | *(required)* | OpenSearch domain hostname |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint |
| `AWS_REGION` | `us-east-1` | AWS region |

---

## s3_document_fetcher.py

**Role:** Low-level AWS S3 document access — list, read, download, upload, and sync files in an S3 bucket.

### Overview

`s3_document_fetcher.py` provides the `S3DocumentFetcher` class used by `document_indexer.py` to retrieve runbooks from S3. It is a thin wrapper around `boto3`'s S3 client with consistent error handling and optional extension filtering.

### Class: `S3DocumentFetcher`

| Method | Description |
|---|---|
| `__init__(bucket_name, prefix, region)` | Initialises a `boto3` S3 client scoped to the given bucket and prefix |
| `list_documents(extension=None)` | Paginates through bucket objects, returns a list of `{key, size, last_modified, filename, path}` dicts. Optional `extension` filter (e.g. `".md"`) |
| `download_document(key, local_path=None)` | Downloads a single object to `/tmp/<filename>` by default. Returns the local path on success |
| `read_document(key)` | Reads an object body directly into memory and returns it as a UTF-8 string (falls back to Latin-1) |
| `upload_document(local_path, s3_key=None)` | Uploads a local file to `{prefix}{filename}` by default. Returns `True` on success |
| `get_document_metadata(key)` | Returns `{key, size, last_modified, content_type, metadata}` for a single object |
| `sync_directory(local_dir, s3_prefix=None)` | Recursively uploads all files in a local directory preserving relative paths. Returns count of files uploaded |

---

## dashboard.py

**Role:** Flask web application providing the analyst-facing report history dashboard and query audit trail (port 5000).

### Overview

`dashboard.py` serves a browser UI at `http://localhost:5000` that lets operators browse past analysis reports, download plain-text versions, and trigger on-demand analysis runs. It also exposes the `/latest_query` page, which renders the most recent query-mode result including the generated DSL, allowing analysts to audit and reproduce any AI-generated answer in OpenSearch Dev Tools.

### Routes

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Renders `templates/dashboard.html` — main report list view |
| `GET` | `/api/reports` | Returns a JSON list of all `analysis_*.json` files with metadata |
| `GET` | `/api/report/<report_id>` | Returns the full JSON content of a specific report |
| `GET` | `/api/report/<report_id>/download` | Serves the `.txt` version of a report as a file download |
| `GET` | `/api/stats` | Returns aggregate statistics: total reports, counts by type, RAG-enabled count, error count, and whether analysis is currently running |
| `GET` | `/api/latest` | Returns the most recent report's full JSON |
| `POST` | `/api/trigger` | Spawns a background thread that runs `python -u main_rag.py --once`. Returns 409 if already running |
| `GET` | `/api/trigger/status` | Returns `{"analysis_running": bool}` |
| `GET` | `/health` | Returns `{"status": "healthy", "timestamp": "..."}` |
| `GET` | `/latest_query` | Renders an inline HTML page showing the most recent query-mode result (question, explanation, generated DSL, aggregations, sample hits) |

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `OUTPUT_DIR` | `/app/output` | Directory scanned for `analysis_*.json` reports |
| `DASHBOARD_PORT` | `5000` | Port the Flask server listens on |

---

## Module Dependency Map

```
api_server.py
  ├── main_rag.py
  │     ├── opensearch_integration.py
  │     └── rag_module.py
  ├── query_generator.py
  └── opensearch_executor.py
        └── opensearch_integration.py (via client arg)

rag_indexer.py  (standalone CLI)
  └── opensearch_integration.py (via get_client())

document_indexer.py  (standalone CLI)
  ├── s3_document_fetcher.py
  └── rag_module.py

dashboard.py  (standalone Flask app)
  └── (spawns main_rag.py --once as subprocess)

main_opensearch.py  (standalone agent, not used by current stack)
  └── opensearch_integration.py

main.py  (standalone agent, basic stack only)
  └── (no internal imports)
```
