"""The cadence guard: layered frequency governance for proactive messages.

The runtime used one 10-minute cooldown; this guard replaced it with layers:

1. global cooldown between any two proactive messages;
2. question cooldown after a question was sent;
3. same-topic-group cooldown, so rephrasing the same subject cannot bypass it;
4. unanswered suppression when the last proactive message got no reply;
5. formal focus-session gate (hard events exempt).

There is no daily cap on how many messages go out: how often to speak is a
policy the caller learns (e.g. from whether messages get replies), not a
fixed number.

It is a pure decision unit: it reads a state mapping and never writes it.
The caller owns persistence and replay.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Optional

from .config import CadenceConfig
from .topic_groups import group_for_topic_label, is_eligible_for_group_cooldown
from .topics import classify_topic

QuestionDetector = Callable[[str], bool]
TopicClassifier = Callable[[str, str, str], str]
FocusSessionProvider = Callable[[], bool]

_QUESTION_MARK_RE = re.compile(r"[？?]")
_QUESTION_FINAL_PARTICLE_RE = re.compile(r"(?:吗|嘛|么|没|呢|吧)\s*[。…！!~～]*$")
_CLAUSE_SPLIT_RE = re.compile(r"[，,。！？!?；;：:\n]")


def looks_like_question(text: str) -> bool:
    """Whether the final text is actually asking the user something.

    The intent name alone is not enough: ``share_thought`` messages can end
    with a question. A question mark is decisive; otherwise only the final
    clause's sentence-final particle counts, so mid-sentence words like
    ``什么`` do not turn statements into questions.
    """
    raw = str(text or "").strip()
    if not raw:
        return False
    if _QUESTION_MARK_RE.search(raw):
        return True
    clauses = [clause.strip() for clause in _CLAUSE_SPLIT_RE.split(raw) if clause.strip()]
    if not clauses:
        return False
    return bool(_QUESTION_FINAL_PARTICLE_RE.search(clauses[-1]))


@dataclass
class CadenceVerdict:
    """Result of one cadence check. ``allowed=False`` means defer."""

    allowed: bool
    reason: str = ""
    retry_after_minutes: int = 30

    @classmethod
    def allow(cls) -> "CadenceVerdict":
        return cls(allowed=True)

    @classmethod
    def block(cls, reason: str, retry_after_minutes: int) -> "CadenceVerdict":
        return cls(
            allowed=False,
            reason=reason,
            retry_after_minutes=max(5, int(retry_after_minutes)),
        )


class CadenceGuard:
    """Layered proactive-message frequency governance.

    Args:
        config: Tunables. Defaults match the runtime.
        focus_session_provider: Optional zero-argument callable returning
            whether a formal focus session is active. The library does not
            know about any study subsystem; inject it. Exceptions are treated
            as "not active" so cadence never breaks the caller.
        topic_classifier: Optional ``(intent, planned_topic, sent_content) ->
            label`` callable. Defaults to the built-in keyword classifier.
        question_detector: Optional text -> bool detector. Defaults to
            :func:`looks_like_question`.
    """

    def __init__(
        self,
        config: Optional[CadenceConfig] = None,
        *,
        focus_session_provider: Optional[FocusSessionProvider] = None,
        topic_classifier: Optional[TopicClassifier] = None,
        question_detector: Optional[QuestionDetector] = None,
    ) -> None:
        self.config = config or CadenceConfig()
        self._focus_session_provider = focus_session_provider
        self._topic_classifier = topic_classifier or classify_topic
        self._question_detector = question_detector or looks_like_question

    # -- config accessors --------------------------------------------------
    @property
    def global_cooldown_seconds(self) -> int:
        return int(self.config.global_cooldown_seconds or 0)

    @property
    def question_cooldown_seconds(self) -> int:
        return int(self.config.question_cooldown_seconds or 0)

    @property
    def same_topic_cooldown_seconds(self) -> int:
        return int(self.config.same_topic_cooldown_seconds or 0)

    @property
    def max_unanswered_proactive(self) -> int:
        return max(0, int(self.config.max_unanswered_proactive or 0))

    @property
    def unanswered_suppress_window_seconds(self) -> int:
        return int(self.config.unanswered_suppress_window_seconds or 0)

    @property
    def exempt_intents(self) -> FrozenSet[str]:
        return frozenset(self.config.exempt_intents)

    @property
    def question_intents(self) -> FrozenSet[str]:
        return frozenset(self.config.question_intents)

    @property
    def group_cooldown_intents(self) -> FrozenSet[str]:
        return frozenset(self.config.group_cooldown_intents)

    # -- entry points ------------------------------------------------------
    def evaluate(
        self,
        *,
        now: float,
        chosen_action: str,
        proactive_state: Optional[Dict[str, Any]] = None,
        planned_topic: str = "",
        candidate_topic_label: str = "",
        non_response_count: int = 0,
        final_text: str = "",
    ) -> CadenceVerdict:
        """Run all cooldown layers for one prospective proactive message.

        Args:
            now: Current Unix timestamp.
            chosen_action: Selected action/intent name.
            proactive_state: Persisted state with keys ``last_proactive_at``,
                ``last_proactive_type``, ``last_proactive_replied`` and
                ``last_sent_topic``.
            planned_topic: Topic the decision layer intends to talk about.
            candidate_topic_label: Pre-computed ``"<intent>:<subtopic>"`` label.
            non_response_count: Consecutive non-response count (kept for API
                compatibility; the state covers suppression).
            final_text: The generated text, when checking after generation.
                If it actually asks a question, question-class rules apply
                even when the intent name says otherwise.
        """
        state = proactive_state if isinstance(proactive_state, dict) else {}
        intent = str(chosen_action or "").strip()
        if not intent:
            return CadenceVerdict.block("cadence_no_intent", 30)

        if intent in self.exempt_intents:
            return CadenceVerdict.allow()

        if self._formal_focus_session_active():
            return CadenceVerdict.block("formal_focus_session_active", 5)

        text_is_question = bool(final_text) and self._question_detector(final_text)
        is_question = intent in self.question_intents or text_is_question
        in_group_cooldown = intent in self.group_cooldown_intents or text_is_question

        # 1. unanswered suppression -- questions only
        last_replied = bool(state.get("last_proactive_replied", True))
        last_proactive_at = float(state.get("last_proactive_at") or 0.0)
        if (
            is_question
            and self.max_unanswered_proactive >= 1
            and not last_replied
            and last_proactive_at > 0
        ):
            remaining = self.unanswered_suppress_window_seconds - (now - last_proactive_at)
            if remaining > 0:
                retry_minutes = min(
                    max(15, int(remaining / 60) + 5),
                    self.question_cooldown_seconds // 60,
                )
                return CadenceVerdict.block("last_proactive_unanswered", retry_minutes)

        last_sent_ts = float(state.get("last_proactive_at") or state.get("last_sent_ts") or 0.0)

        # 2. global cooldown
        if last_sent_ts > 0 and (now - last_sent_ts) < self.global_cooldown_seconds:
            remaining = int(self.global_cooldown_seconds - (now - last_sent_ts))
            return CadenceVerdict.block(
                "cadence_global_cooldown", max(10, int(remaining / 60) + 1)
            )

        # 3. question cooldown
        if is_question:
            last_type = str(state.get("last_proactive_type") or "").strip()
            if (
                last_type in self.question_intents
                and last_proactive_at > 0
                and (now - last_proactive_at) < self.question_cooldown_seconds
            ):
                remaining = int(self.question_cooldown_seconds - (now - last_proactive_at))
                return CadenceVerdict.block(
                    "cadence_question_cooldown", max(15, int(remaining / 60) + 1)
                )

        # 4. same topic group
        if in_group_cooldown:
            current_group = self._resolve_current_group(
                intent, planned_topic, candidate_topic_label
            )
            if current_group and is_eligible_for_group_cooldown(current_group):
                last_group = group_for_topic_label(str(state.get("last_sent_topic") or ""))
                if (
                    last_group == current_group
                    and last_proactive_at > 0
                    and (now - last_proactive_at) < self.same_topic_cooldown_seconds
                ):
                    remaining = int(self.same_topic_cooldown_seconds - (now - last_proactive_at))
                    return CadenceVerdict.block(
                        "cadence_same_topic_group", max(30, int(remaining / 60) + 5)
                    )

        return CadenceVerdict.allow()

    def evaluate_final_text(
        self,
        *,
        now: float,
        intent: str,
        final_text: str,
        proactive_state: Optional[Dict[str, Any]] = None,
        planned_topic: str = "",
        non_response_count: int = 0,
    ) -> CadenceVerdict:
        """Post-generation recheck using the actual text.

        The pre-check runs before the LLM decides, so it has no text and can
        only see the intent. This recheck classifies the generated text into a
        topic label first, then reuses every layer in :meth:`evaluate`.
        """
        candidate_topic_label = ""
        text = str(final_text or "").strip()
        if text:
            try:
                candidate_topic_label = self._topic_classifier(
                    str(intent or "").strip(), planned_topic, text
                )
            except Exception:  # noqa: BLE001 - classification must never block
                candidate_topic_label = ""
        return self.evaluate(
            now=now,
            chosen_action=intent,
            proactive_state=proactive_state,
            planned_topic=planned_topic,
            candidate_topic_label=str(candidate_topic_label or ""),
            non_response_count=non_response_count,
            final_text=text,
        )

    # -- internals ---------------------------------------------------------
    def _formal_focus_session_active(self) -> bool:
        if self._focus_session_provider is None:
            return False
        try:
            return bool(self._focus_session_provider())
        except Exception:  # noqa: BLE001 - cadence must not fail closed on infra errors
            return False

    def _resolve_current_group(
        self, intent: str, planned_topic: str, candidate_topic_label: str
    ) -> str:
        """Resolve this message's topic group.

        Priority: candidate label -> planned topic -> ``general``.
        """
        if candidate_topic_label:
            group = group_for_topic_label(candidate_topic_label)
            if group != "general":
                return group
        if planned_topic and planned_topic.strip():
            try:
                label = self._topic_classifier(intent, planned_topic, "")
                return group_for_topic_label(label)
            except Exception:  # noqa: BLE001
                pass
        return "general"


__all__ = ["CadenceGuard", "CadenceVerdict", "looks_like_question"]
