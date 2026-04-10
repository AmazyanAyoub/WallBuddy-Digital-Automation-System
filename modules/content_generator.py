import os
import json
import logging
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── LLM client (Gemini via reverse-engineered OpenAI-compatible endpoint) ─────

def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="gemini-2.0-flash",
        temperature=0,
        api_key="dummy",
        base_url="http://localhost:3001/openai/v1",
    )


# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Etsy SEO copywriter specializing in digital wall art listings.
You write titles, descriptions, and tags that rank well on Etsy search and convert browsers into buyers.
Always respond with valid JSON only — no markdown, no explanation, just the JSON object."""

def _build_prompt(set_name: str, image_count: int) -> str:
    set_label = f"set of {image_count}" if image_count > 1 else "single print"
    return f"""Write an Etsy listing for a digital wall art product.

Product details:
- Name: {set_name}
- Type: {set_label} ({image_count} high-resolution printable image{"s" if image_count > 1 else ""})
- Available sizes: 24x36, 18x24, 16x20, A1, 11x14 (all included in one download)
- Format: Instant digital download, JPG files, 300 DPI

Return a JSON object with exactly these three fields:

{{
  "title": "...",
  "description": "...",
  "tags": ["...", "...", ...]
}}

Rules:
- title: 120 to 140 characters, include keywords like wall art, printable, poster, instant download, and mention set of {image_count} if more than 1 image. No ALL CAPS.
- description: 150 to 250 words. Cover: what it is, who it's for, where it fits (home/office/cafe), what sizes are included, how instant download works. Natural tone, no fluff.
- tags: exactly 13 tags. Each tag is 2 to 3 words, no commas inside a single tag. Focused on Etsy search terms for wall art buyers.
"""


# ── Validation ────────────────────────────────────────────────────────────────

def _validate(data: dict) -> list[str]:
    """Returns list of validation error strings. Empty list = all good."""
    errors = []

    title = data.get("title", "")
    if not (120 <= len(title) <= 140):
        errors.append(f"Title length {len(title)} — must be 120–140 chars")

    description = data.get("description", "")
    word_count = len(description.split())
    if not (150 <= word_count <= 250):
        errors.append(f"Description word count {word_count} — must be 150–250 words")

    tags = data.get("tags", [])
    if len(tags) != 13:
        errors.append(f"Tag count {len(tags)} — must be exactly 13")
    for tag in tags:
        if "," in tag:
            errors.append(f"Tag contains comma: '{tag}'")

    return errors


def _extract_json(text: str) -> dict:
    """Extracts the JSON object from the model response, strips markdown if present."""
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_content(set_name: str, image_count: int) -> dict:
    """
    Calls Gemini (via OpenAI-compatible endpoint) to generate Etsy listing content.
    Validates the response. Retries once if validation fails.

    Returns dict with keys: title, description, tags
    Raises RuntimeError if both attempts fail validation.
    """
    llm    = _get_llm()
    prompt = _build_prompt(set_name, image_count)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    for attempt in range(1, 3):  # max 2 attempts
        logging.info(f"[{set_name}] Content generation attempt {attempt}/2...")

        response = llm.invoke(messages)
        raw      = response.content

        try:
            data = _extract_json(raw)
        except json.JSONDecodeError as e:
            logging.warning(f"[{set_name}] JSON parse error on attempt {attempt}: {e}")
            continue

        errors = _validate(data)
        if not errors:
            logging.info(f"[{set_name}] Content validated — title: {len(data['title'])} chars, "
                         f"desc: {len(data['description'].split())} words, tags: {len(data['tags'])}")
            return data

        logging.warning(f"[{set_name}] Validation failed on attempt {attempt}: {errors}")
        # Add validation errors to the next prompt so the model self-corrects
        messages.append(response)
        messages.append(HumanMessage(
            content=f"Your response had these issues: {errors}. Please fix and return the corrected JSON only."
        ))

    raise RuntimeError(f"[{set_name}] Content generation failed after 2 attempts")
