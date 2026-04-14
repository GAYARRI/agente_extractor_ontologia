import json
import sys

def safe_load_json(text, source_name="unknown", default=None):
    if text is None:
        print(f"[JSON ERROR] source={source_name} text is None", file=sys.stderr)
        return default

    if not isinstance(text, str):
        print(f"[JSON ERROR] source={source_name} text is not str: {type(text)}", file=sys.stderr)
        return default

    text = text.strip()
    if not text:
        print(f"[JSON ERROR] source={source_name} text is empty", file=sys.stderr)
        return default

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[JSON ERROR] source={source_name} error={e}", file=sys.stderr)
        print(f"[JSON ERROR] raw_text_start={repr(text[:500])}", file=sys.stderr)
        return default