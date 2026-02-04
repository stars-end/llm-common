# Agent Lightning Integration Analysis

**Date**: 2026-01-31
**Epic**: llm-98c
**Feature-Key**: llm-common-agent-lightning

## Executive Summary

This document analyzes Microsoft's **Agent Lightning** framework and defines a comprehensive integration plan for incorporating it into **llm-common**. Agent Lightning is a production-ready framework for training AI agents using reinforcement learning, automatic prompt optimization, and supervised fine-tuning with minimal code changes.

## Agent Lightning Overview

### What is Agent Lightning?

Agent Lightning is "the absolute trainer to light up AI agents" - a framework that enables:

1. **Training Algorithms**
   - Reinforcement Learning (VERL) using vLLM and FSDP
   - Automatic Prompt Optimization (APO) with LLM-driven critique and rewrite
   - Supervised Fine-tuning (SFT)

2. **Framework Agnostic**
   - Works with ANY agent framework (LangChain, OpenAI SDK, AutoGen, CrewAI, Microsoft Agent Framework)
   - Can be used WITHOUT an agent framework (vanilla Python + OpenAI)
   - Selectively optimize specific agents in multi-agent systems

3. **Zero-Code Optimization** (almost!)
   - Drop in `agl.emit_xxx()` helpers or let the tracer collect events
   - Minimal changes to existing agent code

### Architecture Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     Trainer (Orchestrator)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Algorithm   │  │   Runner     │  │ LightningStore │      │
│  │  (The Brain) │  │  (The Worker)│  │  (The Hub)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                  │                │
│         ▼                 ▼                  ▼                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Adapter    │  │   Tracer     │  │   LLM Proxy  │      │
│  │(Data Transform)│ │(Span Capture)│ │(Instrument)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

#### 1. Algorithm (The "Brain")
- Strategy or tuner to train the agent
- Decides what tasks to run
- Learns from results and updates resources (models, prompts)
- Implements training loops (RL, APO, SFT)

#### 2. Runner (The "Worker")
- Executes tasks assigned by the algorithm
- Runs the agent with current resources
- Records results (spans) and rewards
- Manages rollout lifecycle

#### 3. LightningStore (The "Hub")
- Central database and message queue
- Stores: tasks, results, resources, traces
- Enables communication between Algorithm and Runner
- Supports multiple backends (in-memory, SQLite, MongoDB)

#### 4. Tracer (Span Capture)
- Records detailed spans during agent execution
- Automatically instruments LLM calls, tool calls
- Captures: prompts, responses, metadata, rewards
- Uses OpenTelemetry for industry-standard tracing

#### 5. Adapter (Data Transform)
- Converts raw spans into training formats
- Example: `(prompt, response, reward)` triplets for RL
- Bridges store data to algorithm-specific formats

#### 6. LLM Proxy (Optional)
- Centralized endpoint for all LLM calls
- Captures detailed traces of LLM interactions
- Provides unified interface for multiple backends
- Supports dynamic model switching

### Key Concepts

#### Rollout
- Single execution of an agent on a task
- Complete trace from input to result and reward

#### Span
- Unit of work within a rollout (LLM call, tool execution, reward)
- Building blocks of a trace
- Captured by Tracer and sent to Store

#### Reward
- Numeric score (0-1 typically) for rollout quality
- Can be multi-dimensional (accuracy, cost, speed)
- Emitted as special annotation spans

#### Resource
- Assets being tuned (prompts, model weights, proxy endpoints)
- Immutable snapshots with versioning
- Agents perform rollouts against resources

#### Dataset
- Collection of incomplete rollouts (tasks/samples)
- Train/validation datasets for algorithms

### Execution Strategies

#### Shared-Memory Strategy
- Runs algorithm and runner as threads in one process
- Good for debugging
- Not suitable for heavy RL training

#### Client-Server Strategy
- Splits across processes/machines
- Algorithm runs LightningStoreServer (HTTP API)
- Runners connect via LightningStoreClient
- Scalable for distributed training

### Online/Continuous Learning

Unlike batch mode, continuous learning:
- Algorithm doesn't enqueue fixed datasets
- Runners report tasks and spans opportunistically
- Algorithm polls for new data and updates
- Supports real-time agent improvement

## Integration Opportunities for llm-common

### Current llm-common Architecture

```
llm_common/
├── agents/              # Agent implementations
│   ├── orchestrator.py  # Orchestrates agent phases
│   ├── executor.py      # Executes individual tasks
│   ├── research_agent.py
│   ├── tool_selector.py
│   ├── ui_smoke_agent.py
│   └── ...
├── providers/           # LLM provider clients
│   ├── zai_client.py
│   ├── openrouter_client.py
│   └── unified_client.py
├── retrieval/           # RAG interfaces
├── web_search/         # Web search with caching
└── core/               # Core abstractions
```

### High-Impact Integration Points

#### 1. **Agent Training Infrastructure** (P0 - Critical)
- **APO for Prompt Optimization**
  - Automatically improve agent prompts
  - Target: ResearchAgent, ToolSelector, UISmoke agent
  - Use LLM to critique and rewrite prompts based on task performance

- **RL for Decision Making**
  - Train tool selection policies
  - Optimize multi-step planning
  - Learn efficient research strategies

#### 2. **Observability & Telemetry** (P0 - Critical)
- **OpenTelemetry Tracing**
  - Add span emission to all agent phases
  - Capture LLM calls, tool calls, rewards
  - Enable detailed trace analysis

- **LightningStore Integration**
  - Centralized span collection
  - Resource versioning for prompts
  - Queryable trace database

#### 3. **Resource Management** (P1 - High)
- **Prompt Templates**
  - Extract prompts from agent implementations
  - Version and update prompts via APO
  - Support parameterized prompts

- **LLM Proxy**
  - Centralize LLM call instrumentation
  - Capture all LLM interactions
  - Support dynamic model switching

#### 4. **Evaluation & Rewards** (P1 - High)
- **Reward Tracking**
  - Define reward functions for agent actions
  - Multi-dimensional rewards (cost, accuracy, speed)
  - Automatic evaluation via grader functions

- **Grader Functions**
  - Task completion graders
  - Tool usage efficiency graders
  - Cost efficiency graders

### Detailed Integration Mapping

| Agent Lightning Component | llm-common Integration |
|-------------------------|----------------------|
| **LightningStore** | New module: `llm_common/training/store/` |
| **Tracer** | Instrument agents: `llm_common/agents/*` |
| **Algorithm (APO)** | New module: `llm_common/training/algorithms/apo.py` |
| **Algorithm (RL)** | New module: `llm_common/training/algorithms/rl.py` |
| **LLM Proxy** | Integrate into `llm_common/providers/` |
| **Runner** | Use Agent Lightning's LitAgentRunner or adapt |
| **Adapter** | New module: `llm_common/training/adapters/` |
| **Trainer** | New module: `llm_common/training/trainer.py` |

## Implementation Plan

### Phase 1: MVP (v0.8.0) - Core Infrastructure

**Goal**: Enable Automatic Prompt Optimization for llm-common agents

**Subtasks**:
- ✅ llm-98c.1: Research and design integration plan
- ➡️ llm-98c.2: Add Agent Lightning as optional dependency
- ➡️ llm-98c.3: Implement LightningStore adapter
- ➡️ llm-98c.4: Create agent adapters for tracing
- ➡️ llm-98c.5: Implement APO for prompt optimization
- ➡️ llm-98c.7: Implement LLM Proxy
- ➡️ llm-98c.8: Create Trainer wrapper
- ➡️ llm-98c.9: Create training examples
- ➡️ llm-98c.10: Write tests
- ➡️ llm-98c.11: Write documentation

**Deliverables**:
- APO working for ResearchAgent, ToolSelector, UISmoke agent
- Prompt optimization pipelines
- Basic tracing infrastructure
- LightningStore adapter

**Success Criteria**:
- Can optimize prompts for existing agents
- Prompt accuracy improves after APO training
- Traces are captured and queryable

### Phase 2: Full Training (v0.9.0) - RL Integration

**Goal**: Enable Reinforcement Learning for complex decision-making

**Subtasks**:
- ➡️ llm-98c.6: Implement RL (VERL) training
- ➡️ llm-98c.12: Optimize performance and caching

**Deliverables**:
- VERL integration for RL training
- RL environments for tool selection and planning
- Distributed training setup (vLLM + FSDP)
- Performance optimizations

**Success Criteria**:
- Can train agents with RL
- RL policies improve over baselines
- Training scales to multiple GPUs

### Phase 3: Advanced Features (v1.0.0) - Production Ready

**Goal**: Production-grade training infrastructure

**Subtasks**:
- ➡️ llm-98c.13: Plan release strategy
- ➡️ llm-98c.14: Validate integration

**Deliverables**:
- Migration guide for affordabot and prime-radiant-ai
- Feature flags for gradual rollout
- Performance benchmarks
- Comprehensive examples and tutorials

**Success Criteria**:
- affordabot can use training features
- prime-radiant-ai can use training features
- Documentation is comprehensive
- Training performance meets production requirements

## New Module Structure

```
llm_common/
├── training/                    # NEW: Training module
│   ├── __init__.py
│   ├── store/
│   │   ├── __init__.py
│   │   ├── base.py            # LLMCommonStore (LightningStore adapter)
│   │   ├── in_memory.py       # In-memory backend
│   │   └── sqlite.py         # SQLite backend
│   ├── tracer/
│   │   ├── __init__.py
│   │   ├── llm_common_tracer.py
│   │   └── span_emitters.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── span_to_triplet.py # For RL training
│   │   └── trace_to_messages.py # For APO
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── apo.py            # Automatic Prompt Optimization
│   │   └── rl.py             # Reinforcement Learning (VERL)
│   ├── trainer.py             # LLMCommonTrainer
│   ├── rewards.py            # Reward functions and graders
│   └── prompts.py            # Prompt template system
├── providers/                 # MODIFIED: Add proxy support
│   ├── __init__.py
│   ├── proxy.py              # NEW: LLMCommonProxy
│   ├── zai_client.py         # MODIFIED: Add proxy support
│   ├── openrouter_client.py   # MODIFIED: Add proxy support
│   └── unified_client.py    # MODIFIED: Add proxy support
└── agents/                    # MODIFIED: Add tracing
    ├── orchestrator.py        # MODIFIED: Add span emission
    ├── executor.py            # MODIFIED: Add span emission
    ├── research_agent.py      # MODIFIED: Add span emission
    ├── tool_selector.py       # MODIFIED: Add span emission
    └── ui_smoke_agent.py     # MODIFIED: Add span emission
```

## Key Dependencies

### From Agent Lightning
```toml
[tool.poetry.dependencies]
# Existing dependencies...
agentlightning = {version = "^0.3.1", optional = true}

[tool.poetry.extras]
training = ["agentlightning"]
```

### Additional Dependencies
- `opentelemetry-api`: For OpenTelemetry tracing
- `opentelemetry-sdk`: SDK implementation
- `opentelemetry-exporter-otlp`: OTLP exporter
- `vllm`: For VERL RL training (optional)
- `verl`: VERL library for RL (optional)

## Training Workflows

### APO Workflow (Automatic Prompt Optimization)

```python
from llm_common.training import LLMCommonTrainer, APO
from llm_common.agents import ResearchAgent

# 1. Define initial prompt template
initial_prompt = "You are a research assistant. Research: {task}"

# 2. Define grader function
def grader(agent_output, expected_output):
    # Compare agent output with expected
    # Return reward between 0 and 1
    return similarity_score(agent_output, expected_output)

# 3. Create dataset
dataset_train = [ResearchTask(...), ...]
dataset_val = [ResearchTask(...), ...]

# 4. Create APO algorithm
algo = APO(
    openai_client=AsyncOpenAI(),
    prompt_template=initial_prompt,
    grader=grader
)

# 5. Train!
trainer = LLMCommonTrainer(
    algorithm=algo,
    initial_resources={"prompt_template": initial_prompt}
)

trainer.fit(
    agent=ResearchAgent(),
    train_dataset=dataset_train,
    val_dataset=dataset_val
)

# 6. Get optimized prompt
optimized_prompt = trainer.get_latest_resources()["prompt_template"]
```

### RL Workflow (Reinforcement Learning)

```python
from llm_common.training import LLMCommonTrainer, VERLAlgorithm
from llm_common.agents import ToolSelector

# 1. Define reward function
def reward_function(rollout):
    # Multi-dimensional reward
    return {
        "success": 1.0 if rollout.success else 0.0,
        "efficiency": calculate_efficiency(rollout),
        "cost": -calculate_cost(rollout)
    }

# 2. Create RL algorithm
algo = VERLAlgorithm(
    reward_function=reward_function,
    model="glm-4.7",
    vllm_config={...},
    fsdp_config={...}
)

# 3. Train!
trainer = LLMCommonTrainer(algorithm=algo)
trainer.fit(agent=ToolSelector(), dataset=dataset)

# 4. Get trained model
trained_model = trainer.get_latest_resources()["model_weights"]
```

## Benefits

### For affordabot
- **Automated Analysis**: Optimize ResearchAgent prompts for better analysis
- **Cost Reduction**: APO reduces prompt iterations and costs
- **Continuous Improvement**: RL can learn optimal research strategies

### For prime-radiant-ai
- **Better Planning**: Train orchestrator prompts for better task planning
- **Tool Optimization**: Learn which tools to use in different contexts
- **Efficiency**: Optimize execution speed and cost

### General Benefits
- **Observability**: Detailed traces for debugging
- **Automation**: Automatic prompt optimization saves time
- **Scalability**: Train agents at scale with distributed infrastructure
- **Flexibility**: Works with existing agent code (minimal changes)

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| **Complex Integration** | Phase-based approach (MVP first) |
| **Learning Curve** | Comprehensive docs and examples |
| **Performance Overhead** | Optimize tracing (async, caching) |
| **Breaking Changes** | Optional feature flag for gradual rollout |
| **Dependency Bloat** | Use optional dependencies (extras) |

## Success Metrics

### Phase 1 (v0.8.0)
- [ ] APO improves prompt accuracy by >10%
- [ ] Can optimize 3+ agent types
- [ ] Traces are captured for all agent phases
- [ ] Documentation covers all training workflows

### Phase 2 (v0.9.0)
- [ ] RL training works for tool selection
- [ ] Training scales to 4+ GPUs
- [ ] Performance overhead <20%
- [ ] affordabot and prime-radiant-ai can use training

### Phase 3 (v1.0.0)
- [ ] Production-ready with monitoring
- [ ] Migration guide complete
- [ ] Comprehensive examples and tutorials
- [ ] Test coverage >80%

## Next Steps

1. **Review and approve this epic** (llm-98c)
2. **Start Phase 1 implementation** (llm-98c.2 onwards)
3. **Validate APO on ResearchAgent** as first proof-of-concept
4. **Iterate based on findings**
5. **Proceed to Phase 2 and 3**

## References

- **Agent Lightning Repo**: https://github.com/microsoft/agent-lightning
- **Agent Lightning Docs**: https://microsoft.github.io/agent-lightning/
- **Agent Lightning Paper**: https://arxiv.org/abs/2508.03680
- **VERL Docs**: https://verl.readthedocs.io/
- **OpenTelemetry**: https://opentelemetry.io/

---

**Epic ID**: llm-98c
**Feature-Key**: llm-common-agent-lightning
**Pull Request**: https://github.com/stars-end/llm-common/pull/56
