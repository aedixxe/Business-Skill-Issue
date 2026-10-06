"""Behavioral checks for the standalone report renderer."""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/business-skill-issue/scripts/render_pipeline.py"
DEMO = ROOT / "skills/business-skill-issue/examples/demo-pipeline.json"
spec = importlib.util.spec_from_file_location("render_pipeline", SCRIPT)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DEMO.read_text(encoding="utf-8"))
        self.source = DEMO.parent

    def render(self, data=None):
        return renderer.render(self.data if data is None else data, self.source, self.source)

    def test_chronology_and_unknown_event_are_distinct(self):
        page = self.render()
        self.assertLess(page.index("Поступил запрос"), page.index("Получен ответ о замене"))
        self.assertLess(page.index("Появилась новая версия"), page.index("Время события неизвестно</h3>"))
        self.assertLess(page.index("Время события неизвестно</h3>"), page.index("Уточнено время фиксации"))
        self.assertIn("Записано: 13.09.2026", page)

    def test_old_approval_does_not_approve_current_version(self):
        page = self.render()
        self.assertIn("Для текущей версии и её объёма нет решения", page)
        self.assertIn('<span class="pill">Текущая</span>', page)
        changed = copy.deepcopy(self.data)
        changed["project"]["current_version_id"] = "requirements-v1"
        self.assertIn("<h2>Согласовано</h2>", self.render(changed))

    def test_invalid_or_missing_evidence_cannot_claim_approval(self):
        changed = copy.deepcopy(self.data)
        changed["project"]["current_version_id"] = "requirements-v1"
        changed["approvals"][0]["evidence"] = [{"label": "Missing", "path": "missing.md"}]
        self.assertIn("<h2>Нет свидетельства</h2>", self.render(changed))

    def test_conflicting_same_time_decisions_are_unclear(self):
        changed = copy.deepcopy(self.data)
        changed["project"]["current_version_id"] = "requirements-v1"
        rejected = copy.deepcopy(changed["approvals"][0])
        rejected["id"] = "decision-v1-rejected"
        rejected["decision"] = "rejected"
        changed["approvals"].append(rejected)
        self.assertIn("<h2>Статус неясен</h2>", self.render(changed))

    def test_unsafe_markup_and_links_are_inert(self):
        changed = copy.deepcopy(self.data)
        changed["project"]["name"] = '<script>alert("x")</script>'
        changed["events"][0]["artifacts"] = [
            {"label": "Run", "url": "javascript:alert(1)"},
            {"label": "Escape", "path": "../../AGENTS.md"},
        ]
        page = self.render(changed)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn('href="javascript:', page)
        self.assertIn("ссылка недоступна", page)

    def test_markdown_preview_escapes_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "danger.md").write_text("# Demo\n<script>alert(1)</script>", encoding="utf-8")
            changed = copy.deepcopy(self.data)
            changed["events"][0]["artifacts"] = [{"label": "Danger", "path": "danger.md"}]
            page = renderer.render(changed, folder, folder)
            self.assertIn("Читать здесь", page)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
            self.assertNotIn("<script>alert(1)</script>", page)

    def test_date_only_and_answer_times(self):
        changed = copy.deepcopy(self.data)
        changed["events"][0]["occurred_at"] = "2026-09-10"
        changed["events"][1]["questions"][0]["answers"][0]["occurred_at"] = None
        page = self.render(changed)
        self.assertIn("10.09.2026</div>", page)
        self.assertNotIn("10.09.2026 00:00", page)
        self.assertIn("Получен: Время неизвестно · Записан: 12.09.2026", page)

    def test_minimal_contract_validation(self):
        for change, error in (
            (lambda d: d["events"].append(copy.deepcopy(d["events"][0])), "duplicate events id"),
            (lambda d: d["stages"][0].update(status="mystery"), "unknown stage status"),
            (lambda d: d["stages"][3].pop("skip_reason"), "needs skip_reason"),
            (lambda d: d["events"][0].update(stage_id="missing"), "unknown stage_id"),
            (lambda d: d["events"][0].update(corrects_event_id="missing"), "unknown corrects_event_id"),
            (lambda d: d["approvals"][0].update(version_id="missing"), "unknown version_id"),
        ):
            with self.subTest(error=error):
                changed = copy.deepcopy(self.data)
                change(changed)
                with self.assertRaisesRegex(ValueError, error):
                    self.render(changed)


if __name__ == "__main__":
    unittest.main()
