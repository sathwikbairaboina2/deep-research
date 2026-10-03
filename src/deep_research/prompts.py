from __future__ import annotations


def plan_prompt(question: str, max_topics: int) -> tuple[str, str]:
    system = (
        f"Split the research question into 2 to {max_topics} distinct sub-topics that together "
        "answer it. Each has a short title and a one-sentence rationale."
    )
    return system, f"Research question: {question}"


def queries_prompt(question: str, topic_title: str, n: int) -> tuple[str, str]:
    system = f"Write {n} web search queries (plain keywords, no operators) for this sub-topic."
    return system, f"Research question: {question}\nSub-topic: {topic_title}"


def extract_prompt(
    question: str,
    topic_title: str,
    sources: list[tuple[str, str, str]],
    max_claims: int = 6,
) -> tuple[str, str]:
    system = (
        "You extract factual claims from sources. Each claim must cite one or more sources by "
        "their label (e.g. S1) with a quote copied EXACTLY, character for character, from that "
        f"source (6 to 80 words). Never paraphrase quotes. Return at most {max_claims} claims."
    )
    blocks = "\n\n".join(f"[{label}] {url}\n<<<\n{text}\n>>>" for label, url, text in sources)
    user = f"Research question: {question}\nSub-topic: {topic_title}\n\nSources:\n\n{blocks}"
    return system, user


def write_prompt(question: str, claims: list[dict], errors: list[str] | None) -> tuple[str, str]:
    system = (
        "Write a concise Markdown report (no title, no footnote section) answering the question "
        "using ONLY the claims listed. After each sentence that uses a claim, add its marker "
        "exactly as shown, e.g. [c:t1-r1-c2]. One id per marker. Never invent ids."
    )
    lines = "\n".join(f"[c:{c['claim_id']}] {c['text']}" for c in claims)
    user = f"Question: {question}\n\nClaims:\n{lines}"
    if errors:
        user += "\n\nYour previous draft failed these checks: " + "; ".join(errors)
    return system, user
