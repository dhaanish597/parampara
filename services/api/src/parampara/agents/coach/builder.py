"""Coach Live system instruction builder and tool declarations (BUILD_PLAN 16.3-16.5)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from parampara.domain.generated import Mode, SkillGraph

PROMPT_PATH = Path(__file__).resolve().parent / "system.md"
MAX_STEPS_COMPACT_CHARS = 2500

COACH_TOOL_DECLARATIONS: list[dict[str, Any]] = [
    {
        "name": "get_current_step",
        "description": (
            "Returns the active step, the coaching mode and which steps are already verified."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "request_step_check",
        "description": (
            "Ask the app to verify that a step is complete. "
            "The result arrives later as a [SYSTEM] message."
        ),
        "parameters": {
            "type": "object",
            "required": ["step_id", "observation"],
            "properties": {
                "step_id": {"type": "string"},
                "observation": {
                    "type": "string",
                    "description": "What you saw, in English, one sentence.",
                },
            },
        },
    },
    {
        "name": "raise_risk",
        "description": "Record that a mistake or hazard is starting. Call right after saying Ruko.",
        "parameters": {
            "type": "object",
            "required": ["step_id", "description"],
            "properties": {
                "step_id": {"type": "string"},
                "hazard_id": {"type": "string"},
                "description": {"type": "string"},
            },
        },
    },
    {
        "name": "give_hint",
        "description": (
            "Fetch the master's own words for a step. "
            "Level 1 is the title, 2 is the instruction, 3 is the master's tip."
        ),
        "parameters": {
            "type": "object",
            "required": ["step_id", "level"],
            "properties": {
                "step_id": {"type": "string"},
                "level": {"type": "integer", "minimum": 1, "maximum": 3},
            },
        },
    },
    {
        "name": "log_question",
        "description": "Record a question the trainee asked and whether a tip answered it.",
        "parameters": {
            "type": "object",
            "required": ["question"],
            "properties": {
                "question": {"type": "string"},
                "tip_id": {"type": "string"},
            },
        },
    },
]


def format_steps_compact(graph: SkillGraph) -> str:
    """Format compact step list strictly under 2,500 characters (BUILD_PLAN 16.4)."""
    lines: list[str] = []
    for s in sorted(graph.steps, key=lambda x: x.order):
        tip = f" Tip: {s.tips[0].text.hi}" if s.tips else ""
        crit = " [CRITICAL]" if s.critical else ""
        lines.append(f"{s.id}. {s.title.hi} ({s.title.en}){crit}: {s.instruction.hi}{tip}")
    compact = "\n".join(lines)
    if len(compact) > MAX_STEPS_COMPACT_CHARS:
        compact = compact[: MAX_STEPS_COMPACT_CHARS - 3] + "..."
    return compact


def format_hazards_compact(graph: SkillGraph) -> str:
    if not graph.hazards:
        return "None"
    return "\n".join(
        f"- {h.id} (step {h.step_id}, {h.severity.value}): "
        f"{h.description.en} -> {h.interrupt_text.hi}"
        for h in graph.hazards
    )


def build_coach_system_instruction(
    *,
    graph: SkillGraph,
    trainee_name: str,
    master_name: str,
    mode: Mode,
    needs_help_steps: list[str],
) -> str:
    lines = [
        ln
        for ln in PROMPT_PATH.read_text(encoding="utf-8").splitlines()
        if not ln.strip().startswith("prompt_version:")
    ]
    template = "\n".join(lines).lstrip()
    return template.format(
        domain=graph.domain.value,
        trainee_name=trainee_name,
        title_hi=graph.title.hi,
        title_en=graph.title.en,
        master_name=master_name,
        steps_compact=format_steps_compact(graph),
        hazards_compact=format_hazards_compact(graph),
        mode=mode.value,
        needs_help_steps=", ".join(needs_help_steps) if needs_help_steps else "none",
    )


def build_live_connect_config(
    *,
    system_instruction: str,
    voice_name: str,
    resumption_handle: str | None = None,
) -> dict[str, Any]:
    return {
        "responseModalities": ["AUDIO"],
        "systemInstruction": system_instruction,
        "tools": [{"functionDeclarations": COACH_TOOL_DECLARATIONS}],
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
        "contextWindowCompression": {
            "triggerTokens": 32000,
            "slidingWindow": {"targetTokens": 16000},
        },
        "sessionResumption": {"handle": resumption_handle},
        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}},
        "realtimeInputConfig": {"automaticActivityDetection": {"disabled": False}},
    }
