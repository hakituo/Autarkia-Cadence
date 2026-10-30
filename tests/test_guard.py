"""Cadence guard behavior tests (no LLM, no network)."""

import time

import pytest

from autarkia_cadence import (
    CadenceConfig,
    CadenceGuard,
    looks_like_question,
)


NOW = 1_800_000_000.0


def state(**overrides):
    base = {
        "last_proactive_at": 0.0,
        "last_proactive_type": "",
        "last_proactive_replied": True,
        "last_sent_topic": "",
    }
    base.update(overrides)
    return base


class TestUnansweredSuppression:
    def test_unanswered_suppresses_question(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 300,
                last_proactive_type="curious_question",
                last_proactive_replied=False,
            ),
        )
        assert verdict.allowed is False
        assert verdict.reason == "last_proactive_unanswered"

    def test_replied_does_not_suppress(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 300,
                last_proactive_type="curious_question",
                last_proactive_replied=True,
            ),
        )
        assert verdict.allowed is False
        assert verdict.reason != "last_proactive_unanswered"

    def test_suppression_expires_after_window(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 7 * 3600,
                last_proactive_type="curious_question",
                last_proactive_replied=False,
            ),
        )
        assert verdict.allowed is True

    def test_suppression_ignores_statements(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="share_thought",
            proactive_state=state(
                last_proactive_at=NOW - 300,
                last_proactive_replied=False,
            ),
        )
        assert verdict.reason == "cadence_global_cooldown"

    def test_max_unanswered_zero_disables_layer(self):
        guard = CadenceGuard(CadenceConfig(max_unanswered_proactive=0))
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 300,
                last_proactive_type="curious_question",
                last_proactive_replied=False,
            ),
        )
        assert verdict.reason != "last_proactive_unanswered"


class TestGlobalCooldown:
    def test_recent_message_blocked(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="share_thought",
            proactive_state=state(last_proactive_at=NOW - 15 * 60),
        )
        assert verdict.allowed is False
        assert verdict.reason == "cadence_global_cooldown"

    def test_message_after_global_cooldown_allowed(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="share_thought",
            proactive_state=state(last_proactive_at=NOW - 41 * 60),
        )
        assert verdict.allowed is True

    def test_legacy_last_sent_ts_key_supported(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="share_thought",
            proactive_state={"last_sent_ts": NOW - 60},
        )
        assert verdict.reason == "cadence_global_cooldown"

    def test_retry_minutes_at_least_ten(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="share_thought",
            proactive_state=state(last_proactive_at=NOW - 39 * 60),
        )
        assert verdict.retry_after_minutes >= 10

    def test_missing_intent_rejected(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(now=NOW, chosen_action="  ")
        assert verdict.allowed is False
        assert verdict.reason == "cadence_no_intent"


class TestQuestionCooldown:
    def test_question_after_question_blocked(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 50 * 60,
                last_proactive_type="curious_question",
                last_proactive_replied=True,
            ),
        )
        assert verdict.allowed is False
        assert verdict.reason == "cadence_question_cooldown"

    def test_question_after_75_minutes_allowed(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 76 * 60,
                last_proactive_type="curious_question",
                last_proactive_replied=True,
            ),
        )
        assert verdict.allowed is True

    def test_statement_after_question_allowed(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="share_thought",
            proactive_state=state(
                last_proactive_at=NOW - 50 * 60,
                last_proactive_type="curious_question",
            ),
        )
        assert verdict.allowed is True

    def test_custom_question_intent_set(self):
        config = CadenceConfig(question_intents=frozenset({"quiz"}))
        guard = CadenceGuard(config)
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="quiz",
            proactive_state=state(
                last_proactive_at=NOW - 50 * 60,
                last_proactive_type="quiz",
            ),
        )
        assert verdict.reason == "cadence_question_cooldown"


class TestSameTopicGroup:
    def meal_state(self):
        return state(
            last_proactive_at=NOW - 45 * 60,
            last_proactive_type="share_thought",
            last_sent_topic="curious_question:food",
        )

    def test_same_group_blocked(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=self.meal_state(),
            candidate_topic_label="curious_question:food",
        )
        assert verdict.allowed is False
        assert verdict.reason == "cadence_same_topic_group"

    def test_different_group_allowed(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=self.meal_state(),
            candidate_topic_label="curious_question:study",
        )
        assert verdict.allowed is True

    def test_planned_topic_resolves_group(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=self.meal_state(),
            planned_topic="你吃饭了吗",
        )
        assert verdict.reason == "cadence_same_topic_group"

    def test_general_group_not_cooled(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 45 * 60,
                last_sent_topic="curious_question:general",
            ),
            candidate_topic_label="curious_question:general",
        )
        assert verdict.allowed is True

    def test_after_same_topic_window_allowed(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 3 * 3600 - 60,
                last_sent_topic="curious_question:food",
            ),
            candidate_topic_label="curious_question:food",
        )
        assert verdict.allowed is True


class TestNoDailyCap:
    def test_many_questions_today_still_allowed_once_cooldowns_pass(self):
        """No daily cap: once every cooldown has passed, another question is allowed."""
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(
                last_proactive_at=NOW - 6 * 3600,
                last_proactive_type="share_thought",
                today_sent_events=[{"sys_prompt_type": "curious_question"}] * 10,
            ),
        )
        assert verdict.allowed is True

    def test_legacy_cap_key_in_mapping_is_ignored(self):
        """Old settings dicts that still carry the cap key keep loading."""
        config = CadenceConfig.from_mapping({"max_curious_question_per_day": 3})
        assert not hasattr(config, "max_curious_question_per_day")


class TestExemptions:
    @pytest.mark.parametrize(
        "intent",
        ["reminder", "goodnight_proactive", "good_morning_proactive", "focus_nudge"],
    )
    def test_hard_events_bypass_cooldowns(self, intent):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action=intent,
            proactive_state=state(last_proactive_at=NOW - 10),
        )
        assert verdict.allowed is True

    def test_question_text_does_not_unexempt_hard_event(self):
        guard = CadenceGuard()
        verdict = guard.evaluate(
            now=NOW,
            chosen_action="user_health_reminder",
            proactive_state=state(last_proactive_at=NOW - 60, last_proactive_replied=False),
            final_text="记得吃药了吗？",
        )
        assert verdict.allowed is True

    def test_custom_exempt_intents_replace_defaults(self):
        guard = CadenceGuard(CadenceConfig(exempt_intents=frozenset({"ping"})))
        assert guard.evaluate(
            now=NOW, chosen_action="ping", proactive_state=state(last_proactive_at=NOW)
        ).allowed
        assert not guard.evaluate(
            now=NOW, chosen_action="reminder", proactive_state=state(last_proactive_at=NOW)
        ).allowed


class TestFocusGate:
    def test_formal_focus_blocks(self):
        guard = CadenceGuard(focus_session_provider=lambda: True)
        verdict = guard.evaluate(
            now=NOW, chosen_action="share_thought", proactive_state=state()
        )
        assert verdict.reason == "formal_focus_session_active"

    def test_formal_focus_keeps_hard_events(self):
        guard = CadenceGuard(focus_session_provider=lambda: True)
        verdict = guard.evaluate(now=NOW, chosen_action="reminder", proactive_state=state())
        assert verdict.allowed is True

    def test_provider_exception_treated_as_inactive(self):
        def broken():
            raise RuntimeError("study subsystem down")

        guard = CadenceGuard(focus_session_provider=broken)
        verdict = guard.evaluate(
            now=NOW, chosen_action="share_thought", proactive_state=state()
        )
        assert verdict.allowed is True


class TestQuestionDetection:
    @pytest.mark.parametrize(
        "text",
        ["你做饭还是点外卖？", "really?", "你吃饭了吗", "今天上班累不累呢"],
    )
    def test_questions_detected(self, text):
        assert looks_like_question(text) is True

    @pytest.mark.parametrize(
        "text",
        ["你说什么我都听着", "今天路上偶遇一只猫", "", "我在炒菜。"],
    )
    def test_statements_not_detected(self, text):
        assert looks_like_question(text) is False

    def test_questioning_share_thought_blocked_when_unanswered(self):
        guard = CadenceGuard()
        verdict = guard.evaluate_final_text(
            now=NOW,
            intent="share_thought",
            final_text="在炒菜。你做饭还是点外卖？",
            proactive_state=state(
                last_proactive_at=NOW - 46 * 60,
                last_proactive_type="curious_question",
                last_proactive_replied=False,
                last_sent_topic="curious_question:food",
            ),
        )
        assert verdict.reason == "last_proactive_unanswered"

    def test_questioning_share_thought_hits_topic_group(self):
        guard = CadenceGuard()
        verdict = guard.evaluate_final_text(
            now=NOW,
            intent="share_thought",
            final_text="你做饭还是点外卖？",
            proactive_state=state(
                last_proactive_at=NOW - 90 * 60,
                last_proactive_type="curious_question",
                last_sent_topic="curious_question:food",
            ),
        )
        assert verdict.reason == "cadence_same_topic_group"

    def test_statement_share_thought_not_escalated(self):
        guard = CadenceGuard()
        verdict = guard.evaluate_final_text(
            now=NOW,
            intent="share_thought",
            final_text="今天路上偶遇一只猫",
            proactive_state=state(
                last_proactive_at=NOW - 45 * 60,
                last_proactive_type="curious_question",
                last_sent_topic="curious_question:food",
            ),
        )
        assert verdict.allowed is True

    def test_custom_question_detector_used(self):
        guard = CadenceGuard(question_detector=lambda text: text.startswith("ASK:"))
        verdict = guard.evaluate_final_text(
            now=NOW,
            intent="share_thought",
            final_text="ASK:今天怎么样",
            proactive_state=state(
                last_proactive_at=NOW - 46 * 60,
                last_proactive_replied=False,
            ),
        )
        assert verdict.reason == "last_proactive_unanswered"

    def test_custom_classifier_used(self):
        calls = []

        def classifier(intent, planned_topic, sent_content):
            calls.append((intent, planned_topic, sent_content))
            return "curious_question:food"

        guard = CadenceGuard(topic_classifier=classifier)
        verdict = guard.evaluate_final_text(
            now=NOW,
            intent="share_thought",
            final_text="今晚吃什么",
            proactive_state=state(
                last_proactive_at=NOW - 90 * 60,
                last_sent_topic="curious_question:food",
            ),
        )
        assert calls and calls[0][0] == "share_thought"
        assert verdict.reason == "cadence_same_topic_group"


class TestVerdict:
    def test_retry_floor_is_five_minutes(self):
        verdict = CadenceGuard().evaluate(
            now=NOW,
            chosen_action="",
        )
        assert verdict.retry_after_minutes >= 5

    def test_allow_has_empty_reason(self):
        verdict = CadenceGuard().evaluate(
            now=NOW, chosen_action="share_thought", proactive_state=state()
        )
        assert verdict.allowed
        assert verdict.reason == ""

    def test_evaluate_is_deterministic(self):
        guard = CadenceGuard()
        payload = dict(
            now=NOW,
            chosen_action="curious_question",
            proactive_state=state(last_proactive_at=NOW - 60),
        )
        assert guard.evaluate(**payload) == guard.evaluate(**payload)


def test_now_float_tolerance():
    """The guard must not depend on wall-clock time."""
    guard = CadenceGuard()
    assert guard.evaluate(now=time.time(), chosen_action="share_thought").allowed


class TestAgendaOpener:
    """A light opener ("you there?") is a question: no repeat while unanswered."""

    def test_unanswered_opener_blocks_another_opener(self):
        verdict = CadenceGuard().evaluate(
            now=NOW,
            chosen_action="agenda_opener",
            proactive_state=state(
                last_proactive_at=NOW - 300,
                last_proactive_type="agenda_opener",
                last_proactive_replied=False,
            ),
        )
        assert verdict.allowed is False
        assert verdict.reason == "last_proactive_unanswered"

    def test_opener_shares_question_cooldown(self):
        verdict = CadenceGuard().evaluate(
            now=NOW,
            chosen_action="agenda_opener",
            proactive_state=state(
                last_proactive_at=NOW - 50 * 60,
                last_proactive_type="curious_question",
                last_proactive_replied=True,
            ),
        )
        assert verdict.allowed is False
        assert verdict.reason == "cadence_question_cooldown"
