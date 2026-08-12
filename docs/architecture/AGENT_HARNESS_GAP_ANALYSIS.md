# LOOT RAIDERS — AGENT HARNESS GAP ANALYSIS & ARCHITECTURE AUDIT
**Document ID:** `docs/architecture/AGENT_HARNESS_GAP_ANALYSIS.md`  
**Status:** Authoritative Discovery Report (Phase 0 Complete)  
**Target Environment:** Project Loot Raiders Existing Codebase  

---

## 1. CURRENT ARCHITECTURE MAP

Loot Raiders is an autonomous, high-velocity AI Deal Intelligence and Telegram Distribution System. The codebase is organized into decoupled, production-tested layers:

```
+-----------------------------------------------------------------------------------+
|                            WEB & DASHBOARD INTERFACE                              |
|   web/server.py | tma_router.py | dashboard/ (React 18 + TS + Tailwind + Vite)    |
+-----------------------------------------+-----------------------------------------+
                                          |
+-----------------------------------------v-----------------------------------------+
|                                LOOT BRAIN AI LAYER                                |
|   loot_brain/agents/ (BaseAgent, DealIntel, Scraper, ScraperHealer, Affiliate, TG) |
|   loot_brain/orchestrator/ (LootBrainOrchestrator, TaskContext, TaskState)        |
|   loot_brain/security/ (SecurityBoundary, PrivilegeScope, InputSanitizer)        |
|   loot_brain/memory/ (MemoryStore, SQLite + Markdown Store)                       |
|   loot_brain/model_router/ (ModelRouter, ContextManager)                         |
|   loot_brain/learning/ (SubconsciousLoop, Policy Optimization)                   |
+-----------------------------------------+-----------------------------------------+
                                          |
+-----------------------------------------v-----------------------------------------+
|                               CORE DEAL ENGINE LAYER                              |
|   deal_engine/scorer.py (Calculate Score, Glitch Detection, Price Velocity)       |
|   deal_engine/deal_processor.py (Scrapling HTTP Fast-Path & Detail Parser)         |
|   deal_engine/notifier.py (Telegram Dispatcher, ASCI Compliance, Channel Router)  |
|   deal_engine/mirroring/ (Listener, Processor, Redis Queue, Deduplicator)        |
+-----------------------------------------+-----------------------------------------+
                                          |
+-----------------------------------------v-----------------------------------------+
|                          PERSISTENCE & DATA STORAGE LAYER                         |
|   database/ (SQLite `loot_raiders.db`, DB Operations, SQLAlchemy Models)          |
|   database/chroma_db/ (ChromaDB Persistent Vector DB + FastEmbed BGE Embeddings) |
|   utils/affiliate.py (Affiliate Link Converter: `lootraiders-21`)                 |
|   utils/semantic_dedup.py (Vector Deduplicator & String Similarity Fallback)      |
+-----------------------------------------------------------------------------------+
```

---

## 2. EXISTING AI & AGENT CAPABILITIES

- **`loot_brain/agents/base_agent.py`**: Enforces a 7-stage agent execution lifecycle:
  `OBSERVE` -> `UNDERSTAND` -> `PLAN` -> `EXECUTE` -> `VERIFY` -> `REPORT` -> `REMEMBER`.
- **`loot_brain/agents/registry.py`**: Central `AgentRegistry` managing agent discovery and task dispatch.
- **`loot_brain/agents/deal_intelligence.py`**: Evaluates deal safety, historical discounts, and recommendation scores (`APPROVE` / `REJECT`).
- **`loot_brain/agents/scraper_agent.py`**: Scrapes and normalizes raw product payloads from retailer URLs.
- **`loot_brain/agents/scraper_healer.py`**: Autonomous self-healing agent repairing broken CSS/XPath selectors.
- **`loot_brain/agents/affiliate_agent.py`**: Converts raw retailer links into monetized affiliate URLs (`lootraiders-21`).
- **`loot_brain/agents/telegram_agent.py`**: Generates Telegram deal formatting, layout copy, and inline buttons.

---

## 3. EXISTING ORCHESTRATION CAPABILITIES

- **`loot_brain/orchestrator/engine.py`**: `LootBrainOrchestrator` executes end-to-end deal processing pipeline.
- **`loot_brain/orchestrator/states.py`**: `TaskContext` enforcing state machine transitions (`PENDING` -> `PLANNING` -> `RUNNING` -> `REVIEW` -> `VERIFIED` -> `COMPLETED` / `FAILED` / `RETRYING`).

---

## 4. EXISTING QUEUES & EVENTS

- **`deal_engine/mirroring/redis_queue.py`**: Redis/Dragonfly reliable queue (`RedisMessageQueue`) for competitor message ingestion and queue retry handling.
- **`web/server.py`**: Server-Sent Events (SSE) stream (`/api/deals/stream`) broadcasting realtime deal discovery events to the dashboard.

---

## 5. EXISTING MEMORY & KNOWLEDGE SYSTEMS

- **`loot_brain/memory/store.py`**: Multi-tiered `MemoryStore` persisting experience, fact, and decision records into `loot_brain_memory.db` and markdown files.
- **`utils/semantic_dedup.py`**: ChromaDB persistent vector database storing product title embeddings (`bge-small-en-v1.5`) for duplicate detection.
- **`database/operations.py`**: Historical low verification and price history tracking in `loot_raiders.db`.

---

## 6. EXISTING MONITORING & TELEMETRY

- **`web/server.py` & `dashboard/`**: REST endpoints (`/api/admin/scrapers`, `/api/admin/telegram`, `/api/admin/affiliate`) and dashboard telemetry UI (`HealthMonitor.tsx`).
- **`check_health.py`**: Autonomous health check verification.

---

## 7. EXISTING RETRY & RECOVERY MECHANISMS

- **`tenacity`**: Retries with exponential backoff on network errors and link unshortening timeouts in `processor.py`.
- **`ScraperHealerAgent`**: Detects broken DOM selectors and attempts auto-repair using fallback selectors matrix.

---

## 8. EXISTING PERMISSIONS & SECURITY BOUNDARIES

- **`loot_brain/security/permissions.py`**: `SecurityBoundary` enforcing Role-Based Access Control (RBAC) tiers: `READ_ONLY`, `SAFE_WRITE`, `SENSITIVE_WRITE`, `ADMIN`.
- **`InputSanitizer`**: Strips prompt injection triggers (`[SYSTEM_INSTRUCTION]`, `<|im_start|>`) and masks sensitive credentials (`[MASKED_TELEGRAM_TOKEN]`, `[MASKED_OPENAI_KEY]`).

---

## 9. EXISTING TESTING & EVALUATION

- **`scripts/quality_gate.py`**: Master Quality Gate verifying compilation, security leaks, and running unit tests.
- **`tests/`**: Unit test suite comprising 126 unit tests covering deduplication, scoring, compliance, and memory systems.

---

## 10. EXISTING MODEL & PROVIDER ROUTING

- **`loot_brain/model_router/router.py`**: Multi-LLM provider router (`ModelRouter`) selecting optimal model based on task requirements, latency, and token budgets.

---

## 11. PROPOSED HARNESS CAPABILITIES (NEW & EXTENDED)

The new Agent Harness Layer will introduce missing control-plane capabilities:

1. **Structured Tool Registry with Side-Effect Safety Levels**: Centralized registry classifying tools into safety tiers: `READ_ONLY`, `LOW_RISK`, `SIDE_EFFECT`, `HIGH_IMPACT`, `IRREVERSIBLE`.
2. **Durable Checkpoint & Trace Recorder**: Enables long-running agent task recovery from process restarts without duplicating side effects.
3. **Failure Classifier & Recovery Engine**: Categorizes failures (`TRANSIENT`, `DATA`, `TOOL`, `RATE_LIMIT`, `LOGIC`) and executes safe autonomous fallback policies.
4. **Token/Cost Accounting & Loop Protection**: Tracks token usage, model costs, and enforces strict iteration/time limits.
5. **Agent Evaluation & Benchmark Framework**: Evaluates tool selection accuracy, schema compliance, and decision quality against reference datasets.
6. **Human Approval & Escalation Gate**: Intercepts `HIGH_IMPACT` and `IRREVERSIBLE` side-effects for human review before execution.
7. **Shadow Mode Execution Runner**: Runs agent planning and evaluation in non-publishing shadow mode to establish baseline confidence.

---

## 12. CAPABILITY CLASSIFICATION MATRIX

| Capability | Classification | Action / Subsystem Responsible |
| :--- | :---: | :--- |
| **Scraping & Product Detail Extraction** | `EXISTS` | **DO NOT IMPLEMENT.** Use `core/engine.py` & `deal_engine/deal_processor.py`. |
| **Deal Scoring & Glitch Detection** | `EXISTS` | **DO NOT IMPLEMENT.** Use `deal_engine/scorer.py`. |
| **Affiliate Link Conversion** | `EXISTS` | **DO NOT IMPLEMENT.** Use `utils/affiliate.py`. |
| **Telegram Publishing & Notifier** | `EXISTS` | **DO NOT IMPLEMENT.** Use `deal_engine/notifier.py`. |
| **Vector & Title Deduplication** | `EXISTS` | **DO NOT IMPLEMENT.** Use `utils/semantic_dedup.py` & ChromaDB. |
| **7-Stage Lifecycle & Agent Base** | `EXISTS` | **CONSUME.** Use `loot_brain/agents/base_agent.py`. |
| **RBAC & Prompt Sanitization** | `EXISTS` | **CONSUME.** Use `loot_brain/security/permissions.py`. |
| **Structured Tool Registry with Safety Tiers** | `PARTIAL` | **EXTEND.** Add `ToolRegistry` with `SideEffectLevel` in `loot_brain/harness/tools.py`. |
| **Durable Checkpoints & Tracing** | `NEW` | **IMPLEMENT.** Add `CheckpointStore` & `TaskExecutionTrace` in `loot_brain/harness/checkpoints.py`. |
| **Failure Classifier & Recovery Policy** | `NEW` | **IMPLEMENT.** Add `FailureClassifier` & `RecoveryEngine` in `loot_brain/harness/recovery.py`. |
| **Cost Accounting & Loop Protection** | `NEW` | **IMPLEMENT.** Add `CostTracker` & `LoopProtector` in `loot_brain/harness/governance.py`. |
| **Agent Evaluation Suite** | `NEW` | **IMPLEMENT.** Add `AgentEvaluator` in `loot_brain/harness/evaluator.py`. |
| **Human Approval Gate** | `NEW` | **IMPLEMENT.** Add `ApprovalGate` in `loot_brain/harness/approval.py`. |
| **Shadow Mode Execution Harness** | `NEW` | **IMPLEMENT.** Add `ShadowRunner` in `loot_brain/harness/shadow.py`. |

---

## 13. EXACT FILES RESPONSIBLE FOR EXISTING CAPABILITIES

- **Scraping**: `core/engine.py`, `deal_engine/deal_processor.py`, `selectors.json`
- **Scoring**: `deal_engine/scorer.py`
- **Deduplication**: `utils/semantic_dedup.py`, `deal_engine/mirroring/deduplicator.py`
- **Affiliate**: `utils/affiliate.py`, `loot_brain/agents/affiliate_agent.py`
- **Telegram Dispatch**: `deal_engine/notifier.py`, `daily_briefing.py`
- **Database Operations**: `database/operations.py`, `database/db_session.py`, `knowledge_base/models.py`
- **Agent Roster**: `loot_brain/agents/` (`deal_intelligence.py`, `scraper_agent.py`, `scraper_healer.py`, `telegram_agent.py`)
- **Orchestration**: `loot_brain/orchestrator/engine.py`, `loot_brain/orchestrator/states.py`
- **Security & RBAC**: `loot_brain/security/permissions.py`
- **Memory Store**: `loot_brain/memory/store.py`

---

## 14. EXACT FILES TO BE ADDED IN THE HARNESS LAYER

- `loot_brain/harness/__init__.py`: Harness package initialization.
- `loot_brain/harness/tools.py`: Central `ToolRegistry` & `SideEffectLevel` contracts.
- `loot_brain/harness/checkpoints.py`: `CheckpointStore` & `TaskExecutionTrace`.
- `loot_brain/harness/recovery.py`: `FailureClassifier` & `RecoveryEngine`.
- `loot_brain/harness/governance.py`: `CostTracker` & `LoopProtector`.
- `loot_brain/harness/approval.py`: `ApprovalGate` for high-impact actions.
- `loot_brain/harness/shadow.py`: `ShadowRunner` mode execution.
- `loot_brain/harness/evaluator.py`: `AgentEvaluator` benchmark framework.
- `tests/test_agent_harness.py`: Comprehensive test suite for the new Agent Harness.

---

## 15. RISK AUDIT & SAFEGUARDS

1. **Dependency Risks**:
   - **ZERO new external agent frameworks** (No LangChain, AutoGen, CrewAI, or OpenAI Agents SDK). Built entirely using Python standard library, Pydantic, and existing Loot Raiders dependencies.

2. **Database Risks**:
   - Zero destructive schema migrations. Extends existing SQLite databases (`loot_raiders.db`, `loot_brain_memory.db`) with new lightweight checkpoint and audit trace tables.

3. **Performance Risks**:
   - Fast-path deterministic policy evaluation for tool calls and permissions; LLM calls restricted to complex reasoning tasks.

4. **Security Risks**:
   - Enforces RBAC permissions, masks credentials via `InputSanitizer`, and isolates scraped web data from prompt instructions.

---

## 16. RECOMMENDED IMPLEMENTATION ORDER

1. **Phase 1: Tool Registry & Safety Contracts** (`tools.py`)
2. **Phase 2: Checkpoints & Trace Recording** (`checkpoints.py`)
3. **Phase 3: Failure Classification & Recovery Engine** (`recovery.py`)
4. **Phase 4: Governance, Cost Tracking & Loop Protection** (`governance.py`)
5. **Phase 5: Human Approval & Escalation Gate** (`approval.py`)
6. **Phase 6: Shadow Runner & Evaluation Framework** (`shadow.py`, `evaluator.py`)
7. **Phase 7: Comprehensive Integration & Unit Test Suite** (`tests/test_agent_harness.py`)

---

## 17. EXPLICIT LIST OF THINGS THAT MUST NOT BE CHANGED

1. **DO NOT MODIFY** scraper parsing logic in `core/engine.py` or `deal_engine/deal_processor.py`.
2. **DO NOT MODIFY** deal scoring formula or glitch calculation in `deal_engine/scorer.py`.
3. **DO NOT MODIFY** deduplication algorithms in `utils/semantic_dedup.py` or `deal_engine/mirroring/deduplicator.py`.
4. **DO NOT MODIFY** affiliate tag injection (`lootraiders-21`) in `utils/affiliate.py`.
5. **DO NOT MODIFY** Telegram API sending methods or ASCI disclosure footers in `deal_engine/notifier.py`.
6. **DO NOT MODIFY** existing database schemas or SQLAlchemy models in `knowledge_base/models.py`.
7. **DO NOT BREAK** any of the 126 existing unit tests in `tests/`.
