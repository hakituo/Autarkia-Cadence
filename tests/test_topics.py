"""Topic labelling and group mapping tests."""

import pytest

from autarkia_cadence import (
    classify_topic,
    detect_topic_category,
    group_for_subtopic,
    group_for_topic_label,
    is_eligible_for_group_cooldown,
    topic_to_state_slot,
)


class TestDetectTopicCategory:
    @pytest.mark.parametrize(
        "text,category",
        [
            ("该睡了，别熬夜", "SLEEP"),
            ("外卖点了吗", "FOOD"),
            ("英语复习开始了没", "STUDY"),
            ("车该加油了", "VEHICLE"),
            ("晚安", "GREETING"),
            ("早上好", "GREETING"),
        ],
    )
    def test_known_categories(self, text, category):
        assert detect_topic_category(text) == category

    def test_empty_is_unknown(self):
        assert detect_topic_category("") == "unknown"
        assert detect_topic_category("   ") == "unknown"

    def test_unmatched_is_other(self):
        assert detect_topic_category("今天路上偶遇一只猫") == "other"

    def test_highest_score_wins(self):
        # Two food keywords vs one study keyword.
        assert detect_topic_category("外卖和饭") == "FOOD"

    def test_custom_keyword_table(self):
        table = {"CUSTOM": ["猫咪", "小狗"]}
        assert detect_topic_category("我家猫咪", table) == "CUSTOM"
        assert detect_topic_category("今天天气", table) == "other"


class TestClassifyTopic:
    def test_planned_topic_wins(self):
        assert classify_topic("share_thought", "外卖还没点") == "share_thought:food"

    def test_sent_content_used_when_no_plan(self):
        assert classify_topic("curious_question", "", "你吃饭了吗") == "curious_question:food"

    def test_intent_default_when_no_text(self):
        assert classify_topic("bio_complaint") == "bio_complaint:health"
        assert classify_topic("curious_question") == "curious_question:probe"
        assert classify_topic("do_nothing") == "do_nothing:none"

    def test_unknown_intent_defaults_general(self):
        assert classify_topic("mystery") == "mystery:general"

    def test_empty_intent_falls_back(self):
        assert classify_topic("") == "share_thought:general"

    def test_other_category_does_not_override_default(self):
        assert classify_topic("bio_complaint", "今天天气不错") == "bio_complaint:health"

    def test_custom_keywords(self):
        table = {"BODY": ["头疼"]}
        assert classify_topic("share_thought", "我有点头疼", keywords=table) == "share_thought:body"


class TestTopicStateSlot:
    def test_slot_extraction(self):
        assert topic_to_state_slot("curious_question:food") == "food"

    def test_missing_colon_is_general(self):
        assert topic_to_state_slot("food") == "general"
        assert topic_to_state_slot("") == "general"

    def test_empty_subtopic_is_general(self):
        assert topic_to_state_slot("intent:") == "general"


class TestTopicGroups:
    @pytest.mark.parametrize(
        "subtopic,group",
        [
            ("food", "meal"),
            ("sleep", "sleep"),
            ("peer", "social"),
            ("task", "general"),
            ("probe", "general"),
            ("general", "general"),
            ("", "general"),
        ],
    )
    def test_subtopic_mapping(self, subtopic, group):
        assert group_for_subtopic(subtopic) == group

    def test_unknown_subtopic_is_general(self):
        assert group_for_subtopic("astrology") == "general"

    def test_label_parsing(self):
        assert group_for_topic_label("curious_question:food") == "meal"
        assert group_for_topic_label("food") == "meal"
        assert group_for_topic_label("") == "general"

    @pytest.mark.parametrize("group", ["meal", "sleep", "study", "health", "social"])
    def test_specific_groups_eligible(self, group):
        assert is_eligible_for_group_cooldown(group) is True

    @pytest.mark.parametrize("group", ["general", "", None])
    def test_general_group_ineligible(self, group):
        assert is_eligible_for_group_cooldown(group) is False
