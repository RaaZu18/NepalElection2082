#!/usr/bin/env python3
"""
scripts/fetch.py
----------------
Called by GitHub Actions every ~2 minutes.
Calls Anthropic API with web_search tool → saves result to data.json
Reads ANTHROPIC_API_KEY from environment (set as GitHub Secret).
"""

import os, json, sys, urllib.request, urllib.error
from datetime import datetime, timezone

API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
if not API_KEY:
    print("ERROR: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
    sys.exit(1)

PROMPT = """Nepal held its general election on March 5, 2026 (Falgun 21, 2082 BS). Vote counting began immediately. Results are being declared constituency by constituency.

Search the web RIGHT NOW for the latest Nepal election 2082 results.

Search for:
1. "Nepal election 2082 results party seats won 2026"
2. "Nepal election result March 2026 RSP NC UML seats"
3. "nepal election 2082 constituency results today"

Return ONLY a valid JSON object — no markdown, no explanation, nothing before or after the JSON:

{
  "asOf": "date/time from search e.g. March 6 2026 18:45 NPT",
  "status": "counting",
  "turnout": "~62%",
  "parties": [
    {"id":"RSP","won":0,"lead":0},
    {"id":"NC","won":0,"lead":0},
    {"id":"UML","won":0,"lead":0},
    {"id":"NCP","won":0,"lead":0},
    {"id":"RPP","won":0,"lead":0},
    {"id":"JSP","won":0,"lead":0},
    {"id":"UNP","won":0,"lead":0},
    {"id":"IND","won":0,"lead":0}
  ],
  "constituencies": [
    {
      "num": "KTM-1",
      "name": "Kathmandu-1",
      "dist": "Kathmandu",
      "prov": "Bagmati",
      "pct": 85,
      "dec": false,
      "cands": [
        {"n": "Candidate Full Name", "p": "RSP", "v": 18234},
        {"n": "Second Candidate",    "p": "NC",  "v": 7891},
        {"n": "Third Candidate",     "p": "UML", "v": 4312}
      ]
    }
  ],
  "provinces": [
    {"name":"Koshi",         "seats":28,"lead":{"RSP":0,"UML":0,"NC":0},"districts":"14 districts — Jhapa, Morang, Sunsari, Ilam, Taplejung, Panchthar, Terhathum, Dhankuta, Sankhuwasabha, Solukhumbu, Bhojpur, Khotang, Udayapur, Okhaldhunga"},
    {"name":"Madhesh",       "seats":32,"lead":{"JSP":0,"NC":0,"UML":0},"districts":"8 districts — Sarlahi, Dhanusha, Mahottari, Siraha, Saptari, Parsa, Bara, Rautahat"},
    {"name":"Bagmati",       "seats":55,"lead":{"RSP":0,"NC":0,"UML":0},"districts":"13 districts — Kathmandu, Lalitpur, Bhaktapur, Kavrepalanchok, Sindhupalchok, Rasuwa, Nuwakot, Dhading, Makwanpur, Chitwan, Sindhuli, Ramechhap, Dolakha"},
    {"name":"Gandaki",       "seats":28,"lead":{"RSP":0,"NC":0,"UML":0},"districts":"11 districts — Kaski, Tanahun, Syangja, Parbat, Baglung, Myagdi, Mustang, Manang, Lamjung, Gorkha, Nawalpur"},
    {"name":"Lumbini",       "seats":36,"lead":{"RSP":0,"UML":0,"NC":0},"districts":"12 districts — Rupandehi, Dang, Kapilvastu, Palpa, Gulmi, Arghakhanchi, Rolpa, Pyuthan, Rukum East, Banke, Bardiya, Nawalparasi West"},
    {"name":"Karnali",       "seats":24,"lead":{"UML":0,"NC":0,"NCP":0},"districts":"10 districts — Surkhet, Jajarkot, Rukum West, Salyan, Dailekh, Dolpa, Humla, Jumla, Kalikot, Mugu"},
    {"name":"Sudurpashchim", "seats":29,"lead":{"UML":0,"RPP":0,"NC":0},"districts":"9 districts — Kailali, Kanchanpur, Doti, Achham, Bajhang, Bajura, Baitadi, Darchula, Dadeldhura"}
  ],
  "news": [
    {"src":"Source Name","time":"1h ago","tag":"results","hl":"Full headline","sum":"1-2 sentence summary."}
  ],
  "tickers": ["Ticker 1","Ticker 2","Ticker 3","Ticker 4","Ticker 5","Ticker 6"],
  "analysis": "3-4 sentences summarising the current election state based on your live search."
}

STRICT RULES:
- status must be exactly: counting / declared / final
- tag must be exactly: results / parties / analysis
- Fill won/lead with REAL numbers from search — use 0 only if genuinely zero
- Include 8+ real constituencies with real candidate names and real vote counts
- Include 6+ news items
- dec: true if that seat is officially declared
- Return ONLY the JSON — nothing else whatsoever"""


def call_api():
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 4096,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "messages": [{"role": "user", "content": PROMPT}]
    }

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body[:300]}", file=sys.stderr)
        raise


def extract_json(api_response):
    # Collect all text blocks
    text_blocks = [
        b["text"] for b in api_response.get("content", [])
        if b.get("type") == "text"
    ]
    full_text = "\n".join(text_blocks).strip()

    if not full_text:
        raise ValueError("No text content in API response. Stop reason: " +
                         api_response.get("stop_reason", "unknown"))

    # Find JSON object boundaries
    start = full_text.find("{")
    end   = full_text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found in response. Preview:\n" + full_text[:400])

    data = json.loads(full_text[start:end + 1])

    # Validate required fields
    if not isinstance(data.get("parties"), list) or not data["parties"]:
        raise ValueError("parties field missing or empty")
    if not isinstance(data.get("analysis"), str) or not data["analysis"]:
        raise ValueError("analysis field missing")

    return data


def main():
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}] Fetching Nepal election data…")

    try:
        api_resp = call_api()
        data     = extract_json(api_resp)
    except Exception as e:
        print(f"FETCH ERROR: {e}", file=sys.stderr)

        # If data.json already exists, keep it and just update the fetchedAt timestamp
        try:
            with open("data.json") as f:
                existing = json.load(f)
            existing["fetchError"] = str(e)[:200]
            existing["fetchedAt"]  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            with open("data.json", "w") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print("Kept existing data.json (updated timestamp only)")
        except Exception:
            pass  # No existing file — workflow will show loading state

        sys.exit(1)

    # Stamp fetch time
    data["fetchedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data.pop("fetchError", None)  # clear any previous error

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    parties = data.get("parties", [])
    total_seats = sum((p.get("won", 0) + p.get("lead", 0)) for p in parties)
    constituencies = len(data.get("constituencies", []))
    print(f"✓ Saved data.json — status={data.get('status')} | "
          f"total seats tracked={total_seats} | constituencies={constituencies} | "
          f"news items={len(data.get('news', []))}")


if __name__ == "__main__":
    main()