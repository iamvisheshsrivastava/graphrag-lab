"""
LLM-based entity and relation extractor for knowledge graph construction.

Uses google/gemini-2.0-flash-001 via OpenRouter — cheap (~$0.10/1M tokens)
and reliable for structured JSON output.

For each batch of requirements it returns:
  {
    "entities": [{ "id": str, "label": str, "type": str }],
    "relations": [{ "source": str, "target": str, "type": str }]
  }

Entity types: sensor | function | concept | actor | safety_level | standard | system
Relation types: mentions | depends_on | derives_from | implements | governed_by |
                conflicts_with | refines | part_of | uses | connected_to
"""

import os
import json
import logging
import re
from typing import Any, List, Dict

logger = logging.getLogger(__name__)

# gemini-2.0-flash-001: best cost/quality tradeoff for structured JSON extraction
# ~$0.10/1M input tokens; deterministic at temperature=0.0
# Alternatives tried: gemma-4-31b-it:free (unreliable JSON), gpt-4o-mini (slightly pricier)
EXTRACTION_MODEL = "google/gemini-2.0-flash-001"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

EXTRACTION_SYSTEM_PROMPT = """You are a knowledge graph construction engine for automotive ADAS requirements.

Given a list of requirements, extract a unified knowledge graph with:
1. ENTITIES — named technical concepts, systems, sensors, actors, standards, or safety levels
2. RELATIONS — directed edges between requirements and entities, or between entities

Rules:
- Entity IDs must be CamelCase strings with no spaces (e.g. UltrasonicSensor, ASIL_B, ISO26262)
- Use existing requirement IDs (REQ-001 etc.) as source nodes when a requirement references an entity
- Allowed entity types: sensor, function, concept, actor, safety_level, standard, system
- Allowed relation types: mentions, depends_on, derives_from, implements, governed_by, conflicts_with, refines, part_of, uses, connected_to
- Do NOT invent requirement IDs — only use the IDs given in the input
- Extract from meaning, not just keywords — if a requirement implies a dependency, add it
- Be thorough: a good graph has 2-5 entities per requirement on average

Return ONLY valid JSON in this exact schema, no markdown fences:
{
  "entities": [
    {"id": "EntityId", "label": "Human readable label", "type": "sensor|function|concept|actor|safety_level|standard|system"}
  ],
  "relations": [
    {"source": "REQ-001", "target": "EntityId", "type": "relation_type"},
    {"source": "EntityId", "target": "EntityId", "type": "relation_type"}
  ]
}"""


def _get_client():
    try:
        from openai import OpenAI
    except ImportError:
        return None, None

    or_key = os.getenv("OPENROUTER_API_KEY")
    oa_key = os.getenv("OPENAI_API_KEY")

    if or_key:
        client = OpenAI(
            api_key=or_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={"HTTP-Referer": "https://github.com/iamvisheshsrivastava/graphrag-lab"},
        )
        return client, EXTRACTION_MODEL
    elif oa_key:
        client = OpenAI(api_key=oa_key)
        return client, "gpt-4o-mini"
    return None, None


def extract_graph_from_requirements(requirements: List[Dict]) -> Dict[str, Any]:
    """
    Call the LLM to extract entities + relations from a list of requirements.
    Returns { "entities": [...], "relations": [...] } or empty dicts on failure.
    """
    client, model = _get_client()
    if client is None:
        logger.warning("No LLM client available — falling back to keyword extraction")
        return {"entities": [], "relations": []}

    # Format requirements as a compact numbered list for the prompt
    req_lines = []
    for req in requirements:
        req_lines.append(
            f'{req["id"]} [{req.get("type","?")}] [SAE {req.get("sae_level","?")}]: {req["text"]}'
        )
    user_content = "Requirements to extract from:\n\n" + "\n".join(req_lines)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
            temperature=0.0,      # Deterministic
            max_tokens=4096,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model adds them anyway
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        parsed = json.loads(raw)
        entities  = parsed.get("entities", [])
        relations = parsed.get("relations", [])

        logger.info("LLM extracted %d entities, %d relations from %d requirements",
                    len(entities), len(relations), len(requirements))
        return {"entities": entities, "relations": relations}

    except json.JSONDecodeError as e:
        logger.error("LLM returned invalid JSON: %s | raw: %s", e, raw[:300])
        return {"entities": [], "relations": []}
    except Exception as e:
        logger.error("LLM extraction failed: %s", e)
        return {"entities": [], "relations": []}
