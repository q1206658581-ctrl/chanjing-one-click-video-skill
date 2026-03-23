"""
Module C: Script / Copywriting Generator
Produces title, hook, full voiceover script, and CTA from the video plan.
"""

from __future__ import annotations
import json
import os
import re
import math
from pathlib import Path

from schemas import VideoPlan, ScriptResult
from utils import get_logger, timed
import _llm

logger = get_logger("copywriter")

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _load_template(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _stub_script_response() -> str:
    return json.dumps({
        "title": "为什么现在很多老板，开始重新看 AI agent？",
        "hook": "很多老板到现在，还把 AI 当聊天工具，但真正厉害的地方，根本不在聊天。",
        "scene_scripts": [
            "很多老板到现在，还把 AI 当聊天工具，但真正厉害的地方，根本不在聊天。",
            "AI agent 能做的，是直接承担工作流，比如跟进线索、生成报告、处理客服。",
            "它不需要你手把手指挥，它能判断、能决策、能行动。",
            "这就是为什么越来越多老板开始认真研究它：不是跟风，而是真能替团队干活。",
            "你该思考的，不是用不用 AI，而是怎么让 AI 真的走进公司里干活。",
        ],
        "full_script": (
            "很多老板到现在，还把 AI 当聊天工具，但真正厉害的地方，根本不在聊天。\n"
            "AI agent 能做的，是直接承担工作流，比如跟进线索、生成报告、处理客服。\n"
            "它不需要你手把手指挥，它能判断、能决策、能行动。\n"
            "这就是为什么越来越多老板开始认真研究它：不是跟风，而是真能替团队干活。\n"
            "你该思考的，不是用不用 AI，而是怎么让 AI 真的走进公司里干活。"
        ),
        "cta": "你真正该思考的，不是用不用 AI，而是怎么让 AI 真的去公司里干活。",
    }, ensure_ascii=False)


_extract_json = _llm.extract_json


def _extract_scene_scripts(data: dict, scene_count: int) -> list[str]:
    scenes = data.get("scene_scripts")
    if isinstance(scenes, list) and scenes:
        out = [str(x).strip() for x in scenes if str(x).strip()]
        if len(out) >= scene_count:
            return out[:scene_count]
        if len(out) < scene_count:
            out += [""] * (scene_count - len(out))
            return out

    full = str(data.get("full_script", "") or "").strip()
    if not full:
        return [""] * scene_count

    # Try to split by numbered markers like 【1】
    parts = [p.strip() for p in re.split(r"【\s*\d+\s*】", full) if p.strip()]
    if len(parts) == scene_count:
        return parts

    # Fallback: split by lines
    parts = [p.strip() for p in re.split(r"\n+", full) if p.strip()]
    if len(parts) == scene_count:
        return parts

    # Last resort: naive equal chunks by characters
    n = max(scene_count, 1)
    chunk = max(1, math.ceil(len(full) / n))
    return [full[i * chunk:(i + 1) * chunk].strip() for i in range(n)]


def generate_script(plan: VideoPlan) -> ScriptResult:
    """Generate a complete voiceover script from the video plan."""
    if os.environ.get("STUB_MODE") == "1":
        raw = _stub_script_response()
    else:
        template = _load_template("script_prompt.md")

        scene_count = int(plan.scene_count or 5)
        per_scene_sec = float(plan.duration_sec) / max(scene_count, 1)
        target_low = max(8, int(per_scene_sec * 3))
        target_high = max(target_low + 4, int(per_scene_sec * 4))

        prompt = template.format(
            topic=plan.topic,
            industry=plan.industry or "通用",
            platform=plan.platform,
            style=plan.style,
            duration_sec=plan.duration_sec,
            audience=plan.audience,
            core_angle=plan.core_angle,
            tone=plan.tone,
            cta=plan.cta,
            scene_count=scene_count,
            per_scene_sec=round(per_scene_sec, 2),
            per_scene_chars_low=target_low,
            per_scene_chars_high=target_high,
        )
        with timed("generate_script (LLM)", logger):
            raw = _llm.chat(prompt, max_tokens=2048)

    logger.debug("LLM script raw output: %s", raw[:300])
    data = _extract_json(raw)

    scene_count = int(plan.scene_count or 5)
    scene_scripts = _extract_scene_scripts(data, scene_count)
    full_script = str(data.get("full_script", "") or "").strip()
    hook = str(data.get("hook", "") or "").strip()
    if not full_script and any(scene_scripts):
        full_script = "\n".join([s for s in scene_scripts if s])

    if hook and scene_scripts and full_script:
        joined = "".join(scene_scripts)
        if full_script.startswith(hook) and hook not in joined:
            first = scene_scripts[0]
            if len(scene_scripts) == 1:
                scene_scripts[0] = f"{hook}{first}".strip()
            else:
                scene_scripts[0] = hook
                if first:
                    if scene_scripts[1]:
                        scene_scripts[1] = f"{first}{scene_scripts[1]}".strip()
                    else:
                        scene_scripts[1] = first

    result = ScriptResult(
        title=data.get("title", ""),
        hook=data.get("hook", ""),
        full_script=full_script,
        cta=data.get("cta", ""),
        scene_scripts=scene_scripts,
    )
    logger.info("Script generated: title=%r, length=%d chars", result.title, len(result.full_script))
    return result
