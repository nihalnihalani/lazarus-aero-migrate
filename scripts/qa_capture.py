#!/usr/bin/env python3
"""QA capture harness — live-verify a single managed-agent interaction and dump the
EVIDENCE that distinguishes real capabilities from silent no-ops:

  * step-type histogram from BOTH the live stream and the authoritative get() fetch,
  * every google_search_call / google_search_result / url_context_call / url_context_result
    block (count + sample) -> GROUNDING proof,
  * every `thought` block + usage.total_thought_tokens -> THINKING proof,
  * the recovered business rules + a flag for any rule that references a 2nd module.

Not wired into the product; a verification-only tool. Reads GEMINI_API_KEY from env.
Usage: python scripts/qa_capture.py --mode {ground,plain} [--cobol PATH] [--cobol2 PATH]
"""
from __future__ import annotations
import argparse, collections, json, os, pathlib, sys, time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import agent as A  # noqa: E402
from google import genai  # noqa: E402

SEARCH_TYPES = {"google_search_call", "google_search_result",
                "url_context_call", "url_context_result"}


def _typ(obj):
    t = getattr(obj, "type", None)
    if t is None and isinstance(obj, dict):
        t = obj.get("type")
    return t


def _short(obj, n=300):
    try:
        return json.dumps(obj, default=lambda o: getattr(o, "__dict__", str(o)))[:n]
    except Exception:
        return str(obj)[:n]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["ground", "plain"], default="ground")
    ap.add_argument("--cobol", default=str(ROOT / "src" / "sample" / "payroll.cob"))
    args = ap.parse_args()

    if args.mode == "ground":
        os.environ["LAZARUS_GROUND"] = "1"
    else:
        os.environ.pop("LAZARUS_GROUND", None)

    client = genai.Client()
    A.ensure_agent(client)

    cobol = pathlib.Path(args.cobol).read_text()
    prompt = A._build_prompt(cobol, ground=(args.mode == "ground"))

    stream_types = collections.Counter()
    search_blocks = []  # raw search/url blocks seen on the stream
    t0 = time.time()
    interaction_id = None
    completed = None
    for event in client.interactions.create(
        agent="lazarus", input=prompt, stream=True,
        extra_body={"environment": "remote"},
    ):
        interaction_id = getattr(event, "interaction_id", None) or interaction_id
        et = getattr(event, "event_type", None)
        if et in ("step.start", "step.stop"):
            step = getattr(event, "step", None)
            st = _typ(step)
            if st:
                stream_types[st] += 1
            if st in SEARCH_TYPES and len(search_blocks) < 8:
                search_blocks.append((et, st, _short(step)))
        elif et == "interaction.completed":
            completed = getattr(event, "interaction", None)
            interaction_id = getattr(completed, "id", None) or interaction_id

    elapsed = time.time() - t0

    # Authoritative fetch
    fetched = None
    if interaction_id:
        try:
            fetched = client.interactions.get(interaction_id)
        except Exception as e:
            print("GET FAILED:", repr(e)[:300])

    fetched_types = collections.Counter()
    fetched_search = []
    fetched_thought = []
    for s in (getattr(fetched, "steps", None) or []):
        st = _typ(s)
        if st:
            fetched_types[st] += 1
        if st in SEARCH_TYPES and len(fetched_search) < 8:
            fetched_search.append((st, _short(s, 400)))
        if st == "thought" and len(fetched_thought) < 4:
            fetched_thought.append(_short(s, 400))

    usage = getattr(fetched, "usage", None) or getattr(completed, "usage", None)
    thought_tokens = getattr(usage, "total_thought_tokens", None) if usage else None
    total_tokens = getattr(usage, "total_tokens", None) if usage else None

    out_text = A.extract_output_text(fetched or completed, client=client)
    import event_transform as ET  # noqa: E402
    rules = ET.business_rules_from_text(out_text)

    print("\n" + "=" * 70)
    print(f"QA CAPTURE  mode={args.mode}  cobol={pathlib.Path(args.cobol).name}")
    print(f"elapsed={elapsed:.0f}s  interaction_id={interaction_id}")
    print("=" * 70)
    print("STREAM step-type histogram:", dict(stream_types))
    print("FETCH  step-type histogram:", dict(fetched_types))
    n_search = sum(v for k, v in {**stream_types, **fetched_types}.items() if k in SEARCH_TYPES)
    print(f"\n[GROUNDING] search/url blocks (stream+fetch types present): "
          f"{[k for k in {**stream_types, **fetched_types} if k in SEARCH_TYPES]}")
    print(f"[GROUNDING] sample stream search blocks ({len(search_blocks)}):")
    for et, st, body in search_blocks:
        print(f"    {et} {st}: {body}")
    print(f"[GROUNDING] sample fetch search blocks ({len(fetched_search)}):")
    for st, body in fetched_search:
        print(f"    {st}: {body}")
    print(f"\n[THINKING] usage.total_thought_tokens={thought_tokens}  total_tokens={total_tokens}")
    print(f"[THINKING] `thought` step count (fetch)={fetched_types.get('thought', 0)}  "
          f"(stream)={stream_types.get('thought', 0)}")
    for body in fetched_thought:
        print(f"    thought: {body}")
    print(f"\n[RULES] recovered LAZARUS_RULE count={len(rules)}")
    for r in rules:
        print(f"    - {r.get('title')!r} :: cobol_ref={r.get('cobol_ref')!r}")
    # crude cross-module signal: any 'SOURCE:' grounding citations in the text
    n_src = out_text.count("SOURCE:")
    print(f"\n[GROUNDING] inline 'SOURCE:' citations in output text: {n_src}")
    # dump output text tail for manual inspection of search prose
    dump = ROOT / f"qa_capture_{args.mode}.out.txt"
    dump.write_text(out_text)
    print(f"\n[saved] full model output -> {dump}  ({len(out_text)} chars)")


if __name__ == "__main__":
    main()
