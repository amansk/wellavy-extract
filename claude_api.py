#!/usr/bin/env python3
"""Central definitions for talking to the Anthropic Messages API.

Model IDs live here rather than at each call site. The July 2026 outage was a
single retired model ID (`claude-sonnet-4-20250514`) that had been copy-pasted
into seven files, so every one of them had to be found and fixed by hand while
imports were silently returning zero markers.

Model deprecations are announced well in advance and are visible as a
DeprecationWarning from the SDK before the model starts returning 404, so it is
worth reading the warnings the extractors emit at import time.
"""


# Extraction of lab values is the accuracy-critical path: a misread decimal
# place on a creatinine or an A1c flows into the coach and gets acted on, and
# nothing downstream can tell a wrong number from a right one. Opus 5 is the
# strongest model available for document and chart understanding, and volume
# here is a handful of PDFs per import, so the cost difference against a
# cheaper tier is a few cents per import.
EXTRACTION_MODEL = "claude-opus-5"

# Document-type detection only has to answer "is this a blood panel, an InBody
# scan, or neither", so it runs the same model at low effort instead of a
# smaller one: keeping the model consistent means a PDF that the extractor can
# read is never rejected by a weaker classifier upstream.
DETECTION_MODEL = "claude-opus-5"
DETECTION_EFFORT = {"effort": "low"}

# max_tokens is a ceiling on thinking *plus* visible output, and thinking is on
# by default from Opus 5 onward. These are sized well above the largest
# observed response (a ~40-marker panel serialises to roughly 6k tokens) so
# that reasoning cannot crowd out the JSON. Staying at or below ~16k also keeps
# non-streaming requests inside the SDK's HTTP timeout.
EXTRACTION_MAX_TOKENS = 16000
DETECTION_MAX_TOKENS = 4000


class TruncatedResponseError(RuntimeError):
    """The model hit max_tokens before it finished writing its answer."""


class NoTextContentError(RuntimeError):
    """The response carried no text block to read."""


def first_text(response) -> str:
    """Return the first text block of a Messages API response.

    Prefer this over `response.content[0].text`. From Opus 5 and Sonnet 5
    onward adaptive thinking is on by default, so `content[0]` is frequently a
    thinking block, and thinking blocks have no `.text` attribute - indexing
    position 0 raises AttributeError against every current model.

    Truncation is raised rather than returned because every caller parses JSON
    out of this string: a response cut off mid-object fails with an opaque
    JSONDecodeError several frames away from the actual cause.
    """
    if getattr(response, "stop_reason", None) == "max_tokens":
        raise TruncatedResponseError(
            "Response hit the max_tokens ceiling before completing. Raise "
            "max_tokens for this call, or reduce the size of the input."
        )

    for block in response.content:
        if getattr(block, "type", None) == "text":
            return block.text

    raise NoTextContentError(
        "Response contained no text block "
        f"(blocks: {[getattr(b, 'type', '?') for b in response.content]})"
    )
