import logging
import re
from typing import Callable, List, Optional
import httpx

from app.core.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    LLMError,
    LLMMessage,
    LLMResponse,
    MissingLLMConfigurationError,
)
from app.services.llm.prompt import INSUFFICIENT_EVIDENCE_RESPONSE

logger = logging.getLogger("cogniva.llm")


_UNSET = object()


class OpenAILLMProvider(BaseLLMProvider):
    """
    Production LLM provider using OpenAI's Chat Completions API via asynchronous httpx.
    Configurable via environment variables (model, api_key, base_url).
    """

    def __init__(
        self,
        api_key: Optional[str] = _UNSET,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self._api_key = settings.OPENAI_API_KEY if api_key is _UNSET else api_key
        self._model = model or settings.LLM_MODEL
        self._base_url = (base_url or settings.OPENAI_BASE_URL or "https://api.openai.com/v1").rstrip("/")
        self._timeout = timeout

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Calls OpenAI chat completion endpoint.
        Fails fast if OPENAI_API_KEY is not configured.
        """
        if not self._api_key or not self._api_key.strip():
            raise MissingLLMConfigurationError(
                "OPENAI_API_KEY is not configured. Set the OPENAI_API_KEY environment variable to enable LLM generation."
            )

        endpoint = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key.strip()}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature if temperature is not None else settings.LLM_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(endpoint, headers=headers, json=payload)

            if response.status_code != 200:
                logger.error(f"OpenAI API call failed with HTTP {response.status_code}: {response.text}")
                raise LLMError(f"OpenAI API error ({response.status_code}): {response.text}")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise LLMError("OpenAI API returned empty choices list.")

            content = choices[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})

            return LLMResponse(
                content=content.strip(),
                model=data.get("model", self._model),
                usage=usage,
            )

        except httpx.RequestError as e:
            logger.error(f"Network error communicating with OpenAI API: {str(e)}", exc_info=True)
            raise LLMError(f"Network communication failure with OpenAI LLM service: {str(e)}")


MOCK_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "her", "here", "hers", "herself", "him",
    "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it", "its",
    "itself", "just", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "now", "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "shouldn't", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "were", "weren't",
    "what", "when", "where", "which", "while", "who", "whom", "why", "with",
    "would", "wouldn't", "you", "your", "yours", "yourself", "yourselves",
}

# Generic framing and document meta words that do not establish topical specificity on their own
MOCK_FRAMING_WORDS = {
    "according", "please", "tell", "explain", "describe", "state", "states",
    "mention", "mentions", "give", "find", "show", "detail", "details",
    "information", "regarding", "based", "per", "question", "answer",
    "summarize", "summary", "overview", "what", "how", "who", "when",
    "where", "why", "which", "whose", "many", "much", "does", "doesnt",
    "document", "documents", "section", "sections", "text", "context",
    "page", "pages", "file", "files", "guideline", "guidelines", "guide",
    "handbook", "policy", "policies", "rule", "rules", "standard", "standards",
    "company", "technologies", "technology", "corp", "corporation", "inc",
    "employee", "employees", "staff", "personnel", "workplace",
    "acme", "cogniva",
}


def _mock_normalize_word(w: str) -> str:
    """Deterministic light stemmer for offline mock relevance testing."""
    w = re.sub(r"[^\w]", "", w.lower())
    if len(w) > 4:
        for suffix in ("ing", "tion", "ment", "ies", "ied", "ed", "es", "s"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 3:
                if suffix == "ies":
                    return w[:-3] + "y"
                return w[:-len(suffix)]
    elif len(w) == 4 and w.endswith("s"):
        return w[:-1]
    return w


MOCK_FRAMING_STEMS = {_mock_normalize_word(w) for w in MOCK_FRAMING_WORDS}


def _mock_word_matches(qs: str, target_stems: set) -> bool:
    """Checks exact or prefix stem match between query stem and candidate stems."""
    if qs in target_stems:
        return True
    return any(
        (min(len(qs), ts_len) >= 4 and (qs.startswith(ts) or ts.startswith(qs)))
        for ts, ts_len in ((t, len(t)) for t in target_stems)
    )


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for tests and offline validation.
    Synthesizes answers grounded strictly on retrieved context by scoring
    candidate evidence passages against the user query.
    Asserts insufficient evidence if relevant evidence is absent or if
    only incidental keyword overlap exists.
    Preserves inspection attributes for test assertions.
    """

    def __init__(
        self,
        model: str = "mock-gpt-4o-mini",
        custom_handler: Optional[Callable[[List[LLMMessage]], str]] = None,
        custom_response: Optional[str] = None,
    ):
        self._model = model
        self.custom_handler = custom_handler
        self.custom_response = custom_response
        self.last_messages: List[LLMMessage] = []
        self.call_count: int = 0

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def provider_name(self) -> str:
        return "mock"

    async def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        self.call_count += 1
        self.last_messages = list(messages)

        if self.custom_response is not None:
            return LLMResponse(content=self.custom_response, model=self._model)

        if self.custom_handler is not None:
            ans = self.custom_handler(messages)
            return LLMResponse(content=ans, model=self._model)

        # Default deterministic mock logic
        user_msg = next((m.content for m in messages if m.role == "user"), "")

        # Extract user query and context block from Cogniva RAG message layout
        query_match = re.search(r"USER QUESTION:\s*\n(.*?)\n+RETRIEVED SOURCE CONTEXT", user_msg, re.DOTALL)
        query = query_match.group(1).strip() if query_match else ""

        context_match = re.search(r"RETRIEVED SOURCE CONTEXT[^\n]*\n(.*?)\n+TASK:", user_msg, re.DOTALL)
        context = context_match.group(1).strip() if context_match else ""

        # Fallback if unformatted test message was provided
        if not query and not context:
            query = user_msg.strip()

        # Check for empty context or insufficient evidence marker
        if not context or "NO_RELEVANT_SOURCES_FOUND" in context:
            return LLMResponse(content=INSUFFICIENT_EVIDENCE_RESPONSE, model=self._model)

        # Parse context into source chunks with citation identifiers [S1], [S2], ...
        source_blocks: List[Tuple[Optional[str], str]] = []
        matches = list(re.finditer(r"\[(S\d+)\]", context))
        if matches:
            for i, m in enumerate(matches):
                cid = m.group(1)
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(context)
                source_blocks.append((cid, context[start:end]))
        else:
            fallback_cid = "S1" if "[S1]" in user_msg else None
            source_blocks.append((fallback_cid, context))

        # Extract candidate text units (clean lines and sentences) from each source chunk
        candidate_units: List[Tuple[Optional[str], str]] = []
        for cid, raw_block in source_blocks:
            lines = raw_block.splitlines()
            content_lines: List[str] = []
            is_in_content = False
            for line in lines:
                line_s = line.strip()
                if not line_s:
                    continue
                if line_s == "Content:" or line_s.startswith("Content:"):
                    is_in_content = True
                    remainder = line_s[len("Content:"):].strip()
                    if remainder:
                        content_lines.append(remainder)
                    continue
                if not is_in_content and any(line_s.startswith(hdr) for hdr in (
                    "Document:", "Page:", "Chunk:", "Similarity:", "Score:", "---"
                )):
                    continue
                content_lines.append(line_s)

            for line_s in content_lines:
                cleaned_line = re.sub(r"^[-*•\d.]+\s*", "", line_s).strip()
                if not cleaned_line:
                    continue
                candidate_units.append((cid, cleaned_line))
                sentences = re.split(r"(?<=[.!?])\s+", cleaned_line)
                if len(sentences) > 1:
                    for s in sentences:
                        s_clean = s.strip()
                        if len(s_clean) >= 15:
                            candidate_units.append((cid, s_clean))

        # Tokenize and normalize query terms
        q_raw_tokens = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1]
        meaningful_q_words = [w for w in q_raw_tokens if w not in MOCK_STOP_WORDS]

        topical_q_words = [w for w in meaningful_q_words if _mock_normalize_word(w) not in MOCK_FRAMING_STEMS]

        is_summary_request = (
            any(w in ("summarize", "summary", "overview") for w in q_raw_tokens)
            and not topical_q_words
        )

        if not meaningful_q_words and not is_summary_request:
            return LLMResponse(content=INSUFFICIENT_EVIDENCE_RESPONSE, model=self._model)

        effective_topical = topical_q_words if topical_q_words else meaningful_q_words
        effective_topical_stems = {_mock_normalize_word(w) for w in effective_topical}

        q_stems = [_mock_normalize_word(w) for w in meaningful_q_words]
        q_stem_set = set(q_stems)

        q_bigrams = [
            (_mock_normalize_word(meaningful_q_words[i]), _mock_normalize_word(meaningful_q_words[i + 1]))
            for i in range(len(meaningful_q_words) - 1)
        ]

        # Score candidate passages deterministically
        best_candidate: Optional[str] = None
        best_cid: Optional[str] = None
        best_score = -1.0

        for cid, passage in candidate_units:
            p_tokens = [w for w in re.findall(r"\w+", passage.lower()) if len(w) > 1]
            if not p_tokens:
                continue
            p_stems = [_mock_normalize_word(w) for w in p_tokens]
            p_stem_set = set(p_stems)

            # Match query stems
            matched_q = {qs for qs in q_stem_set if _mock_word_matches(qs, p_stem_set)}
            matched_topical = matched_q & effective_topical_stems

            # Count bigram matches
            matched_bigrams = 0
            if q_bigrams and len(p_stems) >= 2:
                for b1, b2 in q_bigrams:
                    for j in range(len(p_stems) - 1):
                        if (
                            _mock_word_matches(b1, {p_stems[j]})
                            and _mock_word_matches(b2, {p_stems[j + 1]})
                        ):
                            matched_bigrams += 1
                            break

            if is_summary_request:
                is_sufficient = True
                score = 1.0
            else:
                # Strict sufficiency rules:
                # 1. Must match at least one topical keyword stem
                if not matched_topical:
                    is_sufficient = False
                # 2. Reject single incidental keyword overlap when query has 2+ keywords
                elif len(meaningful_q_words) >= 2 and len(matched_q) < 2 and matched_bigrams == 0:
                    is_sufficient = False
                else:
                    is_sufficient = True

                score = (
                    len(matched_topical) * 4.0
                    + (len(matched_q) - len(matched_topical)) * 1.0
                    + matched_bigrams * 5.0
                    + (len(matched_q) / max(len(q_stem_set), 1)) * 2.0
                )
                for ts in effective_topical_stems:
                    occurrences = sum(1 for ps in p_stems if _mock_word_matches(ts, {ps}))
                    if occurrences > 1:
                        score += 1.0

                if 25 <= len(passage) <= 250:
                    score += 0.5

            if is_sufficient and score > best_score:
                best_score = score
                best_candidate = passage
                best_cid = cid

        # If no candidate passage satisfied sufficiency criteria, return deterministic refusal
        if not best_candidate or best_score <= 0:
            return LLMResponse(content=INSUFFICIENT_EVIDENCE_RESPONSE, model=self._model)

        clean_ans = best_candidate.strip()
        if not re.search(r"[.!?]$", clean_ans):
            clean_ans += "."

        citation_tag = f" [{best_cid}]" if best_cid else (" [S1]" if "[S1]" in user_msg else "")
        answer = f"Based on the provided documents, {clean_ans}{citation_tag}"
        return LLMResponse(content=answer, model=self._model)
