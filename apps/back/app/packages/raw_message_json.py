import re

def raw_message_json(raw) -> str:
    """Text JSON from a structured-output raw message.

    include_raw returns an AIMessage. Passing that object to
    model_validate_json raises a json_type error.
    """
    content = getattr(raw, "content", raw)
    if isinstance(content, list):
        chunks = []
        for block in content:
            if isinstance(block, str):
                chunks.append(block)
            elif isinstance(block, dict):
                chunks.append(str(block.get("text") or block.get("content") or ""))
            else:
                text = getattr(block, "text", None)
                if text:
                    chunks.append(str(text))
        content = "".join(chunks)
    if not isinstance(content, str):
        content = str(content)

    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    return text