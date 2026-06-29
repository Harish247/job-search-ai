import argparse
import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI
from rich import print_json

load_dotenv()

_ROOT = Path(__file__).parent.parent


def load_candidate_profile() -> str:
    local = _ROOT / "candidate_profile.local.yaml"
    default = _ROOT / "candidate_profile.yaml"
    path = local if local.exists() else default

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    def _join(val):
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val) if val is not None else ""

    return "\n".join([
        f"Name: {data.get('name', '')}",
        f"Experience: {_join(data.get('years_of_experience', ''))} years",
        f"Current level: {data.get('current_level', '')}",
        f"Core stack: {_join(data.get('core_stack', []))}",
        f"Domain: {_join(data.get('domain', []))}",
        f"Target roles: {_join(data.get('target_roles', []))}",
        f"Preferences: {_join(data.get('preferences', []))}",
        f"Dealbreakers: {_join(data.get('dealbreakers', []))}",
        f"AI experience: {data.get('ai_experience', '')}",
    ])


def _build_system_prompt(candidate_profile: str) -> str:
    return f"""You are a job description analyst. You evaluate job descriptions on behalf of a specific candidate.

CANDIDATE PROFILE:
{candidate_profile}

Extract structured information from the job description and return valid JSON with exactly these fields:

- company (string)
- role (string)
- level (string) — detect carefully using these signals:
    * Junior: "new grad", "entry level", "0-2 years", "junior", "associate"
    * Mid: "engineer II", "L4", "3-5 years", "mid-level"
    * Senior: "senior engineer", "L5", "5+ years" without staff/lead signals
    * Staff: "staff engineer", "lead", "L6", "IC5", "tech lead", "principal engineer" (if not a people manager title)
    * Principal: "principal", "distinguished", "L7", "IC6", "architect" (individual contributor)
- required_skills (array of strings)
- nice_to_have_skills (array of strings)
- experience_years (number or null if not specified)
- tech_stack (array of strings)
- red_flags (array of strings — anything concerning about the role, company, or fit for this candidate)
- culture_signals (array of strings — hints about team culture, values, work style)
- score_breakdown (object) — score each component out of its maximum weight, with a one-line reason:
    {{
      "tech_stack_match":   {{"score": <0-30>, "reason": "<one line>"}},
      "seniority_match":    {{"score": <0-20>, "reason": "<one line>"}},
      "domain_relevance":   {{"score": <0-20>, "reason": "<one line>"}},
      "ai_skill_gap":       {{"score": <0-15>, "reason": "<one line>"}},
      "culture_logistics":  {{"score": <0-15>, "reason": "<one line>"}}
    }}
    Scoring guide:
    - tech_stack_match (30): overlap between job's required tech and candidate's core stack
    - seniority_match (20): how well the role level aligns with the candidate's current level
    - domain_relevance (20): how useful the candidate's background and domain experience is for this role
    - ai_skill_gap (15): 15 = no AI needed or beginner AI is fine; 0 = heavy ML/LLM expertise required
    - culture_logistics (15): remote-friendly, travel within limits, IC or small team, no major red flags
- match_score (integer 0-100) — sum of all five score_breakdown component scores
- summary (string — 2-3 sentence summary of the role and overall fit for this candidate)

Return only the JSON object, no markdown or explanation."""


SYSTEM_PROMPT = _build_system_prompt(load_candidate_profile())


def extract_jd(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": jd_text},
        ],
        temperature=0,
    )

    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {
            "error": "Failed to parse OpenAI response as JSON",
            "raw_response": raw,
        }


if __name__ == "__main__":
    # parser = argparse.ArgumentParser(description="Extract structured data from a job description file.")
    # parser.add_argument("file_path", help="Path to the job description text file")
    # args = parser.parse_args()
    # file_path = args.file_path

    file_path = "../jds/example.txt"
    result = extract_jd(file_path)
    print_json(json.dumps(result))
