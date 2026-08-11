"""Project-wide translation tool orchestration."""

from __future__ import annotations

from collections.abc import Callable

from locaforge.application.project_workspace import ProjectWorkspace

type ProjectAction = Callable[[], object]
type ActionRunner = Callable[[ProjectAction, str], bool]


class TranslationToolsController:
    """Coordinates validation, replacement, issue dismissal, and cancellation."""

    def __init__(
        self,
        workspace: ProjectWorkspace,
        current_entry_id: Callable[[], str | None],
        is_busy: Callable[[], bool],
        start_validation: Callable[[], object],
        ask_replacement: Callable[[], tuple[str, str] | None],
        confirm_replacement: Callable[[], bool],
        run_action: ActionRunner,
        cancel_translation: Callable[[], bool],
        cancel_review: Callable[[], bool],
        disable_cancel: Callable[[], None],
        show_status: Callable[[str], None],
    ) -> None:
        self._workspace = workspace
        self._current_entry_id = current_entry_id
        self._is_busy = is_busy
        self._start_validation = start_validation
        self._ask_replacement = ask_replacement
        self._confirm_replacement = confirm_replacement
        self._run_action = run_action
        self._cancel_translation = cancel_translation
        self._cancel_review = cancel_review
        self._disable_cancel = disable_cancel
        self._show_status = show_status

    def validate_project(self) -> None:
        if self._can_run():
            self._start_validation()

    def replace_translations(self) -> None:
        if not self._can_run():
            return
        replacement = self._ask_replacement()
        if replacement is None or not self._confirm_replacement():
            return
        search_text, replacement_text = replacement
        self._run_action(
            lambda: self._workspace.replace_translations(search_text, replacement_text),
            "Translations replaced",
        )

    def dismiss_current_ai_review_issue(self) -> None:
        entry_id = self._current_entry_id()
        if entry_id is None:
            return
        self._run_action(
            lambda: self._workspace.dismiss_ai_review_issue(entry_id),
            "AI review issue dismissed",
        )

    def cancel_operation(self) -> None:
        if self._cancel_translation():
            operation = "translation"
        elif self._cancel_review():
            operation = "AI review"
        else:
            return
        self._disable_cancel()
        self._show_status(f"Cancelling {operation} after the current Ollama request...")

    def _can_run(self) -> bool:
        return self._workspace.has_project and not self._is_busy()
