# AGENT_CAPABILITIES.md — UISmoke v1 (glm-4.6v)

This document defines the safe primitives and unsafe patterns for the autonomous QA agent. Authors creating `.yml` stories must adhere to these capabilities to ensure high reliability and attributable results.

## Safe Primitives (Deterministic)

These actions are high-reliability and should be used whenever a stable selector is available.

| Action | Support | Notes |
| :--- | :---: | :--- |
| `navigate` | ✅ | Supports `${ENV}` substitution for secrets/local URLs. |
| `click` | ✅ | Uses Playwright standard click. Avoid on dynamic SVGs. |
| `type` | ✅ | Redacts input in logs if variable substitution is used. |
| `wait_for_selector`| ✅ | Use to stabilize transitions. Default timeout 30s. |
| `assert_text` | ✅ | Case-sensitive body/selector text check. |
| `frame_click` | ✅ | Strict frame isolation for Plaid/Clerk. |
| `frame_type` | ✅ | Secure input into iframes. |
| `scroll` | ✅ | Essential for long dashboards. |

## LLM-Driven Patterns (Agentic)

Use these only when the page state is non-deterministic or requires "Visual Reason" (e.g. Chat/AI responses).

| Pattern | Reliability | Guidance |
| :--- | :---: | :--- |
| **Visual Verification** | 90%+ | "Verify the graph shows a upward trend" |
| **Multi-step Reasoning**| 85% | "Find the highest gainer and click it" |
| **Form Filling (AI)** | 80% | Use deterministic `type` for P0 login flows. |

## Known Gaps & Unsafe Patterns (DO NOT USE)

| Pattern | Mitigation |
| :--- | :---: | :--- |
| **Canvas Interaction** | Use `assert_text` on legend if possible; Canvas is a visual-only black box. |
| **Hover-heavy Flows** | Prefer direct URL navigation to sub-pages if hover is flaky. |
| **Third-party Popups** | (e.g. OAuth) Use the Auth Bypass standard to skip third-party UI. |

## Baseline Calibration Results (EPIC 3)

| Target | Pass Rate | Mode |
| :--- | :---: | :---: |
| **POC Suite (14 Primitives)** | 100% | Deterministic |
| **Auth Bypass** | 100% | Cookie/Bearer |
| **Iframe (Plaid)** | 100% | Frame-Action |

---
*Created as part of [bd-7coo.3.4]*
