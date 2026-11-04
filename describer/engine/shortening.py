"""Conservative narration shortening: remove only redundant visual lead-ins.

No summarization, fact deletion, recurrence deduplication or model call occurs.
Unrecognized wording is left intact and uses the existing pause fallback.
"""
import re


def concise(text):
    match=re.match(r'^(?:The (?:scene|shot|frame) shows|We (?:can see|see)|You can see)\s+(.+)$',text.strip(),re.DOTALL)
    if not match:return text
    remainder=match[1]
    # A complete visible noun phrase is required; avoid transforming questions,
    # negation scoped over "shows", quotations or arbitrary conjunctions.
    if not re.match(r'(?:a|an|the|two|three|four|five|several|some)\s+\w',remainder,re.I):return text
    return remainder[0].upper()+remainder[1:]
