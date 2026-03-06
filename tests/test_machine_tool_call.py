"""End-to-end state machine tests for requires_tool_call mode."""

from ratchet_sm import (
    FailAction,
    State,
    StateMachine,
    ToolCallMissingAction,
    ValidAction,
)
from ratchet_sm.prompts.require_tool_call_default import (
    NO_TOOL_CALL_TEMPLATE,
    PSEUDO_CALL_TEMPLATE,
)
from ratchet_sm.strategies.require_tool_call_feedback import RequireToolCallFeedback


def make_machine(max_attempts=3):
    return StateMachine(
        states={"call": State(name="call", requires_tool_call=True, max_attempts=max_attempts)},
        transitions={},
        initial="call",
    )


class TestPseudoCallRecovery:
    def test_xml_tag_valid_json_returns_valid_action(self):
        m = make_machine()
        action = m.receive('<tool_call>{"name": "search"}</tool_call>')
        assert isinstance(action, ValidAction)
        assert action.parsed == {"name": "search"}
        assert action.format_detected == "pseudo_tool_call"

    def test_function_call_tag_valid_json_returns_valid_action(self):
        m = make_machine()
        action = m.receive('<function_call>{"name": "fn", "args": {}}</function_call>')
        assert isinstance(action, ValidAction)
        assert action.parsed == {"name": "fn", "args": {}}

    def test_labelled_fence_valid_json_returns_valid_action(self):
        m = make_machine()
        action = m.receive('```tool_call\n{"name": "do_thing"}\n```')
        assert isinstance(action, ValidAction)
        assert action.parsed == {"name": "do_thing"}

    def test_bracket_tag_valid_json_returns_valid_action(self):
        m = make_machine()
        action = m.receive('[TOOL_CALL]{"name": "x"}[/TOOL_CALL]')
        assert isinstance(action, ValidAction)
        assert action.parsed == {"name": "x"}

    def test_plain_json_no_tag_returns_valid_action(self):
        """Plain JSON body without tag → ParseJSON fallback in TOOL_CALL_PIPELINE."""
        m = make_machine()
        action = m.receive('{"name": "search"}')
        assert isinstance(action, ValidAction)
        assert action.parsed == {"name": "search"}

    def test_valid_action_marks_machine_done(self):
        m = make_machine()
        m.receive('<tool_call>{"name": "x"}</tool_call>')
        assert m.done is True


class TestToolCallMissingAction:
    def test_invalid_json_in_tag_returns_tool_call_missing(self):
        m = make_machine()
        action = m.receive("<tool_call>not valid json</tool_call>")
        assert isinstance(action, ToolCallMissingAction)
        assert action.reason == "pseudo_tool_call_in_text"
        assert action.prompt_patch == PSEUDO_CALL_TEMPLATE

    def test_plain_text_returns_tool_call_missing(self):
        m = make_machine()
        action = m.receive("Sure, I will search for that.")
        assert isinstance(action, ToolCallMissingAction)
        assert action.reason == "no_tool_call"
        assert action.prompt_patch == NO_TOOL_CALL_TEMPLATE

    def test_empty_string_returns_tool_call_missing(self):
        m = make_machine()
        action = m.receive("")
        assert isinstance(action, ToolCallMissingAction)
        assert action.reason == "no_tool_call"

    def test_errors_tuple_not_empty(self):
        m = make_machine()
        action = m.receive("plain text")
        assert isinstance(action, ToolCallMissingAction)
        assert len(action.errors) > 0

    def test_machine_not_done_after_missing(self):
        m = make_machine()
        m.receive("plain text")
        assert m.done is False


class TestMaxAttempts:
    def test_exceeding_max_attempts_returns_fail_action(self):
        m = make_machine(max_attempts=2)
        m.receive("plain text")  # attempt 1
        m.receive("plain text")  # attempt 2
        action = m.receive("plain text")  # attempt 3 → FailAction
        assert isinstance(action, FailAction)
        assert m.done is True

    def test_fail_action_reason_mentions_max_attempts(self):
        m = make_machine(max_attempts=1)
        m.receive("plain text")   # attempt 1
        action = m.receive("plain text")  # attempt 2 → FailAction
        assert isinstance(action, FailAction)
        assert "max_attempts" in action.reason

    def test_history_preserved_in_fail_action(self):
        m = make_machine(max_attempts=1)
        m.receive("plain text")
        fail_action = m.receive("plain text")
        assert isinstance(fail_action, FailAction)
        assert len(fail_action.history) >= 1


class TestReset:
    def test_reset_clears_attempts(self):
        m = make_machine(max_attempts=2)
        m.receive("plain text")  # attempt 1
        m.reset()
        action = m.receive('<tool_call>{"name": "x"}</tool_call>')
        assert isinstance(action, ValidAction)

    def test_reset_after_done(self):
        m = make_machine()
        m.receive('<tool_call>{"name": "x"}</tool_call>')
        assert m.done is True
        m.reset()
        assert m.done is False
        action = m.receive('<tool_call>{"name": "y"}</tool_call>')
        assert isinstance(action, ValidAction)


class TestRequiresToolCallFalse:
    """Ensure requires_tool_call=False (default) retains existing behaviour."""

    def test_invalid_input_returns_retry_action(self):
        from ratchet_sm import RetryAction

        m = StateMachine(
            states={"s": State(name="s")},
            transitions={},
            initial="s",
        )
        action = m.receive("plain text without json")
        assert isinstance(action, RetryAction)
        assert not isinstance(action, ToolCallMissingAction)

    def test_valid_json_returns_valid_action(self):
        m = StateMachine(
            states={"s": State(name="s")},
            transitions={},
            initial="s",
        )
        action = m.receive('{"key": "value"}')
        assert isinstance(action, ValidAction)


class TestCustomStrategy:
    def test_custom_strategy_overrides_default(self):
        """Explicit strategy= takes precedence over requires_tool_call default."""
        custom = RequireToolCallFeedback(no_call_template="MY CUSTOM PROMPT")
        m = StateMachine(
            states={
                "call": State(
                    name="call",
                    requires_tool_call=True,
                    strategy=custom,
                )
            },
            transitions={},
            initial="call",
        )
        action = m.receive("plain text")
        assert isinstance(action, ToolCallMissingAction)
        assert action.prompt_patch == "MY CUSTOM PROMPT"


class TestCustomNormalizers:
    def test_custom_normalizers_override_tool_call_pipeline(self):
        """Explicit normalizers= takes precedence over requires_tool_call pipeline."""
        from ratchet_sm.normalizers import DEFAULT_PIPELINE

        m = StateMachine(
            states={
                "call": State(
                    name="call",
                    requires_tool_call=True,
                    normalizers=DEFAULT_PIPELINE,
                )
            },
            transitions={},
            initial="call",
        )
        # YAML would succeed with DEFAULT_PIPELINE but not TOOL_CALL_PIPELINE
        action = m.receive("```yaml\nname: search\n```")
        assert isinstance(action, ValidAction)
        assert action.parsed == {"name": "search"}


class TestClassifier:
    """Unit tests for _classify_tool_call_failure."""

    def test_xml_tag_bad_json_is_pseudo(self):
        from ratchet_sm.machine import _classify_tool_call_failure

        assert _classify_tool_call_failure("<tool_call>bad json</tool_call>") == "pseudo_tool_call_in_text"

    def test_labelled_fence_bad_json_is_pseudo(self):
        from ratchet_sm.machine import _classify_tool_call_failure

        assert _classify_tool_call_failure("```tool_call\nbad\n```") == "pseudo_tool_call_in_text"

    def test_bracket_tag_bad_json_is_pseudo(self):
        from ratchet_sm.machine import _classify_tool_call_failure

        assert _classify_tool_call_failure("[TOOL_CALL]bad[/TOOL_CALL]") == "pseudo_tool_call_in_text"

    def test_plain_text_is_no_tool_call(self):
        from ratchet_sm.machine import _classify_tool_call_failure

        assert _classify_tool_call_failure("Here is my answer.") == "no_tool_call"

    def test_empty_is_no_tool_call(self):
        from ratchet_sm.machine import _classify_tool_call_failure

        assert _classify_tool_call_failure("") == "no_tool_call"

    def test_plain_json_no_tag_is_no_tool_call(self):
        from ratchet_sm.machine import _classify_tool_call_failure

        assert _classify_tool_call_failure('{"name": "search"}') == "no_tool_call"
