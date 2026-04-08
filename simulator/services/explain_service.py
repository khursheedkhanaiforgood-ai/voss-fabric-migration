"""
ExplainService — on-demand "why" explanations using Claude API.

Pattern mirrors the Cisco-EN CLI Agent orchestrator:
  1. Build context from step metadata (replaces pgvector RAG for Sprint 1)
  2. Inject VOSS system prompt (guardrails)
  3. Call Claude API
  4. Return formatted explanation

Fallback: if ANTHROPIC_API_KEY is not set, returns the built-in step.why field.
Sprint 2 will replace the context-building step with pgvector RAG lookup.
"""

from __future__ import annotations
import os
from simulator.models.migration_step import MigrationStep, THEMES


# ── VOSS System Prompt (mirrors Cisco-EN system_master.md) ────────────────────
VOSS_SYSTEM_PROMPT = """You are a VOSS/FabricEngine expert assistant embedded in the FabricEngine Flight Simulator.

Your role: explain WHY network concepts and commands work the way they do in VOSS/FabricEngine.
The student has completed the EXOS/SwitchEngine lab and is migrating to VOSS.

Rules:
1. Always relate VOSS concepts back to their EXOS equivalent (what changed and why)
2. Cite the governing IEEE standard or RFC when explaining a protocol concept
3. Keep explanations to 3-5 sentences — focused and actionable
4. If asked about a command, explain what it does AND what happens if it is missing or wrong
5. Never fabricate VOSS CLI syntax — if unsure, say "verify in VOSS CLI Reference Guide"
6. Zero-hallucination policy: if a concept is outside your knowledge, say so explicitly

Tone: Professional, direct, like a senior network engineer explaining to a peer.
Do not use bullet points — explain in connected prose.
"""


class ExplainService:
    """
    Sprint 1: lightweight Claude API explanation with step context as RAG substitute.
    Sprint 2: replace _build_context() with pgvector corpus lookup.
    """

    def __init__(self):
        self._client = None
        self._api_available = False
        self._try_init_client()

    def _try_init_client(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
            self._api_available = True
        except ImportError:
            pass

    def explain(self, query: str, step: MigrationStep, sw_id: str) -> str:
        """
        Return explanation for the query in the context of the current step.
        Falls back to step.why if API is not available.
        """
        if not self._api_available:
            return self._fallback(step, query)

        context = self._build_context(step, sw_id, query)
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=400,
                system=VOSS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": context}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            return f"{self._fallback(step, query)}\n\n_(Live explanation unavailable: {e})_"

    def _build_context(self, step: MigrationStep, sw_id: str, query: str) -> str:
        """
        Build the RAG-substitute context from step metadata.
        Sprint 2: this becomes a pgvector cosine search → format_context() call.
        """
        theme_meta = THEMES.get(step.theme, {})
        cmds = step.expected_commands.get(sw_id, [])
        cmd_list = "\n".join(f"  {c}" for c in cmds) if cmds else "  (narrative step — no CLI commands)"

        return f"""Current migration step: {step.number}/18 — {step.name}
Theme (functional bin): {step.theme} — {theme_meta.get('label', '')}
Phase: {step.phase.value}
Active switch: {sw_id}

Step description: {step.description}

Built-in explanation: {step.why}

EXOS parallel (what the student already knows): {step.exos_parallel}

Governing standard: {step.standard}
Standard URL: {step.standard_url}

Expected CLI commands for {sw_id}:
{cmd_list}

Student question: {query}

Answer the student's question in the context of this specific migration step.
Connect to the EXOS background where relevant. Cite the standard if applicable."""

    def _fallback(self, step: MigrationStep, query: str) -> str:
        """Return built-in why explanation when API is not available."""
        base = step.why if step.why else step.description
        return (
            f"{base}\n\n"
            f"_(Set ANTHROPIC_API_KEY for live AI explanations tailored to your question.)_"
        )
