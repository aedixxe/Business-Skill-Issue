#!/usr/bin/env python3
"""Render one Business Skill Issue pipeline JSON as a standalone local HTML file."""

from __future__ import annotations

import argparse
import html
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit


STAGE_LABELS = {
    "pending": "Не начат",
    "in_progress": "В работе",
    "blocked": "Блокируется",
    "done": "Завершён",
    "skipped": "Пропущен",
}
DECISION_LABELS = {
    "requested": "Запрошено",
    "approved": "Согласовано",
    "rejected": "Отклонено",
    "changes_requested": "Нужны правки",
}
EVENT_LABELS = {
    "intake": "Запрос", "questions": "Вопросы", "answers": "Ответ",
    "document": "Документ", "approval": "Согласование", "design": "Проектирование",
    "build": "Реализация", "acceptance": "Приёмка", "change": "Изменение",
    "correction": "Исправление", "general": "Событие",
}
QUESTION_LABELS = {"open": "Открыт", "answered": "Есть ответ", "partial": "Частичный ответ"}


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def date_key(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def show_date(value: object) -> str:
    parsed = date_key(value)
    if not parsed:
        return "Время неизвестно"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
        return esc(parsed.strftime("%d.%m.%Y"))
    date_format = "%d.%m.%Y %H:%M %Z" if isinstance(value, str) and re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value) else "%d.%m.%Y %H:%M"
    return esc(parsed.strftime(date_format).strip())


def safe_local_target(value: object, source_dir: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or value.startswith(("/", "\\")):
        return None
    if "?" in value:
        return None
    local_path, _, fragment = value.partition("#")
    local_path = unquote(local_path)
    if not local_path or "\\" in local_path or "\x00" in local_path:
        return None
    try:
        target = (source_dir / local_path).resolve(strict=True)
        target.relative_to(source_dir.resolve())
    except (ValueError, OSError, RuntimeError):
        return None
    if not target.is_file():
        return None
    return target


def safe_href(value: object, source_dir: Path, output_dir: Path) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        return html.escape(value, quote=True)
    if parsed.scheme.lower() == "mailto" and parsed.path and not parsed.netloc:
        return html.escape(value, quote=True)
    target = safe_local_target(value, source_dir)
    if not target:
        return None
    _, _, fragment = value.partition("#")
    relative = os.path.relpath(target, output_dir.resolve())
    href = quote(relative, safe="/.-_")
    if fragment:
        href += "#" + quote(unquote(fragment), safe="-._~")
    return html.escape(href, quote=True)


def artifact(item: object, source_dir: Path, output_dir: Path) -> str:
    if not isinstance(item, dict):
        return ""
    label = esc(item.get("label") or "Документ")
    raw = item.get("path") or item.get("url")
    href = safe_href(raw, source_dir, output_dir)
    target = safe_local_target(item.get("path"), source_dir) if item.get("path") else None
    preview = ""
    if target and target.suffix.lower() in {".md", ".txt"}:
        if target.stat().st_size <= 256 * 1024:
            try:
                contents = target.read_text(encoding="utf-8")
                preview = f'<details class="doc-preview"><summary>Читать здесь</summary><pre>{esc(contents)}</pre></details>'
            except UnicodeDecodeError:
                preview = '<span class="muted">Просмотр недоступен: файл не в UTF-8.</span>'
        else:
            preview = '<span class="muted">Файл больше 256 КиБ; откройте его отдельно.</span>'
    version = item.get("version_id")
    version_html = f'<span class="muted"> · версия {esc(version)}</span>' if version else ""
    if href:
        return f'<li><a href="{href}" rel="noopener noreferrer">{label}</a>{version_html}{preview}</li>'
    return f'<li><span>{label}</span>{version_html}<span class="missing"> · ссылка недоступна</span></li>'


def artifacts(items: object, source_dir: Path, output_dir: Path) -> str:
    if not isinstance(items, list) or not items:
        return ""
    rows = "".join(artifact(item, source_dir, output_dir) for item in items)
    return f'<ul class="artifacts">{rows}</ul>' if rows else ""


def text_list(items: object, empty: str = "Не указаны") -> str:
    if not isinstance(items, list) or not items:
        return f'<span class="muted">{esc(empty)}</span>'
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items if item) + "</ul>"


def question_block(items: object, source_dir: Path, output_dir: Path) -> str:
    if not isinstance(items, list) or not items:
        return ""
    parts = []
    for question in items:
        if not isinstance(question, dict):
            continue
        answers = question.get("answers") if isinstance(question.get("answers"), list) else []
        answers_html = []
        for answer in answers:
            if not isinstance(answer, dict):
                continue
            source = answer.get("source")
            link = safe_href(source, source_dir, output_dir)
            source_html = f' · <a href="{link}" rel="noopener noreferrer">Источник</a>' if link else (f" · {esc(source)}" if source else "")
            answers_html.append(f'<li>{esc(answer.get("text") or "Ответ без текста")}<small>Получен: {show_date(answer.get("occurred_at"))} · Записан: {show_date(answer.get("recorded_at"))}{source_html}</small></li>')
        answer_body = "<ul>" + "".join(answers_html) + "</ul>" if answers_html else '<p class="muted">Ответ пока не зафиксирован.</p>'
        qid = f'<span class="question-id">{esc(question["id"])}</span> ' if question.get("id") else ""
        qstatus = QUESTION_LABELS.get(str(question.get("status")), question.get("status") or "Статус не указан")
        parts.append(f'<div class="qa"><strong>{qid}{esc(question.get("text") or "Вопрос без текста")}</strong><span class="pill">{esc(qstatus)}</span>{answer_body}</div>')
    return '<div class="questions"><h4>Вопросы и ответы</h4>' + "".join(parts) + "</div>" if parts else ""


def stage_card(stage: dict, current_id: object) -> str:
    status = str(stage.get("status") or "pending")
    title = esc(stage.get("title") or stage.get("id") or "Этап без названия")
    current = ' current' if stage.get("id") == current_id else ""
    detail_parts = []
    if stage.get("needed_step"):
        detail_parts.append(f'<p><b>Нужный шаг:</b> {esc(stage["needed_step"])}</p>')
    if status == "skipped":
        reason = stage.get("skip_reason") or "Причина не указана"
        detail_parts.append(f'<p><b>Причина пропуска:</b> {esc(reason)}</p>')
    if stage.get("blockers"):
        detail_parts.append(f'<div><b>Блокеры:</b> {text_list(stage["blockers"])}</div>')
    if not detail_parts and status == "pending":
        detail_parts.append('<p class="muted">Ещё не начат.</p>')
    return f'<article class="stage{current}"><div class="stage-top"><h3>{title}</h3><span class="status {esc(status)}">{esc(STAGE_LABELS.get(status, status))}</span></div>{"".join(detail_parts)}</article>'


def event_card(event: dict, source_dir: Path, output_dir: Path, stage_titles: dict) -> str:
    occurred = event.get("occurred_at")
    recorded = event.get("recorded_at")
    kind = event.get("type") or "general"
    when = show_date(occurred)
    recorded_html = f'<span>Записано: {show_date(recorded)}</span>' if recorded else '<span>Время записи неизвестно</span>'
    version = f'<span>Версия: {esc(event["version_id"])}</span>' if event.get("version_id") else ""
    stage = f'<span>Этап: {esc(stage_titles.get(event["stage_id"], event["stage_id"]))}</span>' if event.get("stage_id") else ""
    correction = f'<p class="correction">Исправляет событие {esc(event["corrects_event_id"])}</p>' if event.get("corrects_event_id") else ""
    summary = f'<p>{esc(event["summary"])}</p>' if event.get("summary") else ""
    details = f'<p>{esc(event["details"])}</p>' if event.get("details") else ""
    body = summary + details + correction + question_block(event.get("questions"), source_dir, output_dir) + artifacts(event.get("artifacts"), source_dir, output_dir)
    if not body:
        body = '<p class="muted">Подробности не зафиксированы.</p>'
    opened = " open" if event.get("questions") else ""
    return f'''<article class="event" id="event-{quote(str(event.get("id") or "unknown"), safe="-._~")}">
      <div class="event-time">{when}</div>
      <details{opened}><summary><span class="event-title">{esc(event.get("title") or "Событие без названия")}</span><span class="event-type">{esc(EVENT_LABELS.get(str(kind), kind))}</span></summary>
      <div class="event-body"><div class="event-meta">{recorded_html}{stage}{version}</div>{body}</div></details>
    </article>'''


def approval_summary(data: dict, source_dir: Path, output_dir: Path) -> tuple[str, str]:
    project = data.get("project") or {}
    current_version = project.get("current_version_id") if isinstance(project, dict) else None
    versions = {item.get("id"): item for item in data.get("versions", []) if isinstance(item, dict) and item.get("id")}
    if not current_version or current_version not in versions:
        return "Нет текущей версии", "Укажите project.current_version_id и соответствующую версию."
    scope = versions[current_version].get("scope")
    if not scope:
        return "Объём не указан", "Для вывода о согласовании нужна область действия текущей версии."
    relevant = [item for item in data.get("approvals", []) if isinstance(item, dict) and item.get("version_id") == current_version and item.get("scope") == scope]
    if not relevant:
        return "Не согласовано", "Для текущей версии и её объёма нет решения."
    if any(not date_key(item.get("decided_at")) for item in relevant):
        return "Статус неясен", "У одного из решений нет даты; порядок решений нельзя подтвердить."
    latest_time = max(date_key(item["decided_at"]) for item in relevant)
    latest_candidates = [item for item in relevant if date_key(item["decided_at"]) == latest_time]
    if len(latest_candidates) > 1 and len({item.get("decision") for item in latest_candidates}) > 1:
        return "Статус неясен", "У последних решений одинаковое время и разные исходы."
    latest = latest_candidates[-1]
    decision = latest.get("decision")
    evidence = latest.get("evidence")
    valid_evidence = isinstance(evidence, list) and any(
        isinstance(item, dict) and safe_href(item.get("path") or item.get("url"), source_dir, output_dir)
        for item in evidence
    )
    if decision == "approved" and valid_evidence:
        return "Согласовано", f'Текущая версия {current_version}; решение от {show_date(latest["decided_at"])}. Проверьте свидетельство ниже.'
    if decision == "approved":
        return "Нет свидетельства", "Статус approved есть, но доказательство решения не приложено."
    return DECISION_LABELS.get(str(decision), "Не согласовано"), f'Последнее решение по текущей версии {current_version}.'


def approval_cards(data: dict, source_dir: Path, output_dir: Path) -> str:
    items = data.get("approvals") or []
    if not items:
        return '<p class="muted">Решения пока не зафиксированы.</p>'
    current_version = (data.get("project") or {}).get("current_version_id")
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        historical = item.get("version_id") != current_version
        note = f'<p>{esc(item["note"])}</p>' if item.get("note") else ""
        evidence = artifacts(item.get("evidence"), source_dir, output_dir)
        if not evidence:
            evidence = '<p class="muted">Свидетельство не приложено.</p>'
        parts.append(f'<article class="approval"><div class="approval-top"><b>{esc(DECISION_LABELS.get(str(item.get("decision")), item.get("decision") or "Решение неизвестно"))}</b><span class="pill">{"История" if historical else "Текущая версия"}</span></div><p class="muted">{esc(item.get("version_id") or "Версия неизвестна")} · {esc(item.get("scope") or "Объём неизвестен")} · {show_date(item.get("decided_at"))}</p><p>Кто: {esc(item.get("actor") or "Не указан")}</p>{note}<b>Свидетельство</b>{evidence}</article>')
    return "".join(parts)


CSS = r"""
:root{--ink:#15313d;--muted:#566d76;--line:#c7d9df;--paper:#f1f7f9;--white:#fff;--blue:#126f80;--amber:#966019;--red:#a74739;--green:#2c725d}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{color:var(--blue);text-underline-offset:3px}a:hover{color:#064859}a:focus-visible,summary:focus-visible{outline:3px solid #56b5c0;outline-offset:3px}h1,h2,h3,h4,p{margin-top:0}h1{font-size:clamp(2.2rem,5vw,4.4rem);letter-spacing:-.055em;line-height:1.04;max-width:14ch}h2{font-size:1.35rem;letter-spacing:-.025em}h3{font-size:1rem;margin:0}h4{font-size:.92rem;margin:1rem 0 .45rem}small,.muted{color:var(--muted)}small{display:block;font-size:.78rem;margin-top:.3rem}.eyebrow,.event-time,.event-type,.status,.pill{font:700 .72rem/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.04em}.shell{max-width:1160px;margin:auto;padding:0 28px 80px}.hero{padding:64px 0 44px;border-bottom:2px solid var(--ink);display:grid;grid-template-columns:minmax(0,1fr) minmax(240px,340px);gap:38px}.eyebrow{text-transform:uppercase;color:var(--blue)}.hero p{max-width:58ch}.hero-aside{align-self:end;border-left:3px solid var(--blue);padding:4px 0 4px 20px}.hero-aside strong{display:block;font-size:1.1rem;margin:.25rem 0}.toc{display:flex;flex-wrap:wrap;gap:10px;padding:18px 0;border-bottom:1px solid var(--line)}.toc a{padding:5px 10px;background:#e1eef1;text-decoration:none;font-size:.82rem;font-weight:700}.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:50px;padding-top:42px}.section{margin-bottom:55px}.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:15px;border-bottom:1px solid var(--ink);margin-bottom:20px}.section-head p{font-size:.8rem;color:var(--muted)}.stages{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.stage,.approval,.version{background:var(--white);border:1px solid var(--line);padding:16px 18px}.stage.current{border-left:4px solid var(--blue)}.stage-top,.approval-top{display:flex;justify-content:space-between;align-items:start;gap:10px}.stage p{font-size:.86rem;margin:.65rem 0 0}.stage ul,.approval ul{margin:.4rem 0 0;padding-left:1.2rem}.status,.pill{display:inline-block;padding:3px 7px;white-space:nowrap;background:#e8f1f4;color:var(--blue)}.status.done{background:#e4f1eb;color:var(--green)}.status.blocked{background:#f9e8e4;color:var(--red)}.status.skipped{background:#eef0f1;color:var(--muted)}.status.in_progress{background:#dceff2}.approval-grid{display:grid;gap:9px}.approval{font-size:.86rem}.approval p{margin:.45rem 0}.approval b{font-size:.88rem}.timeline{border-left:2px solid var(--line);margin-left:130px}.event{position:relative;margin:0 0 14px 21px;background:var(--white);border:1px solid var(--line)}.event:before{content:"";position:absolute;left:-28px;top:20px;width:12px;height:12px;border:2px solid var(--blue);background:var(--paper);border-radius:50%}.event-time{position:absolute;right:calc(100% + 46px);top:17px;width:105px;text-align:right;color:var(--muted);letter-spacing:0}.event summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;gap:12px;padding:16px 18px}.event summary::-webkit-details-marker{display:none}.event summary:before{content:"+";color:var(--blue);font-weight:800;margin-right:2px}.event details[open] summary:before{content:"−"}.event-title{font-weight:700;flex:1}.event-type{color:var(--blue);text-transform:uppercase}.event-body{border-top:1px solid var(--line);padding:16px 18px;font-size:.9rem}.event-body p{margin-bottom:.6rem}.event-meta{display:flex;flex-wrap:wrap;gap:5px 16px;font-size:.76rem;color:var(--muted);margin-bottom:12px}.questions{border-top:1px solid var(--line);margin-top:15px}.qa{padding:12px 0;border-top:1px dotted var(--line)}.qa strong{display:block}.qa .pill{margin-top:5px}.qa ul{padding-left:1.2rem}.qa li{margin:.45rem 0}.artifacts{padding-left:1.2rem}.artifacts li{margin:.2rem 0}.missing{color:var(--red)}.correction{padding:8px 12px;border-left:3px solid var(--amber);background:#fff5e7}.unknown{margin-top:24px}.version{margin-bottom:8px;font-size:.87rem}.version p{margin:.45rem 0}.side{position:sticky;top:22px;align-self:start}.callout{background:var(--ink);color:#fff;padding:22px}.callout .eyebrow{color:#8bdee5}.callout h2{font-size:1.18rem;margin:.45rem 0}.callout p{margin:.5rem 0 0}.callout .muted{color:#bdd1d7}.side .mini{font-size:.84rem;border:1px solid var(--line);padding:18px;background:#fff;margin-top:10px}.mini h3{margin-bottom:10px}.mini ul{padding-left:1.1rem;margin:.4rem 0}.footer{border-top:1px solid var(--line);padding-top:18px;font-size:.8rem;color:var(--muted)}
@media(max-width:850px){.layout{grid-template-columns:1fr}.side{position:static;grid-row:1}.hero{grid-template-columns:1fr;padding-top:38px}.hero-aside{align-self:auto}.timeline{margin-left:105px}.event-time{width:80px;right:calc(100% + 38px)}}@media(max-width:580px){.shell{padding:0 16px 50px}.hero{padding-top:30px;gap:22px}.stages{grid-template-columns:1fr}.timeline{margin-left:0;border-left:0}.event{margin-left:0}.event:before{display:none}.event-time{position:static;width:auto;text-align:left;padding:12px 16px 0}.event summary{padding:10px 16px 14px}.event-body{padding:16px}.event-type{font-size:.63rem}.toc{gap:5px}.toc a{font-size:.76rem}}
.question-id{color:var(--blue);font:700 .75rem ui-monospace,SFMono-Regular,Menlo,monospace;margin-right:.3rem}.stage-map{margin-top:18px}.stage-map h2{font-size:1rem;margin:0 0 10px}.side .stages{display:grid;grid-template-columns:1fr;gap:4px}.side .stage{padding:9px 10px;font-size:.82rem}.side .stage-top{align-items:center}.side .stage h3{font-size:.8rem}.side .stage p{font-size:.75rem;margin:.3rem 0 0}.side .stage ul{font-size:.75rem;margin:.2rem 0;padding-left:1rem}.side .status{font-size:.6rem;padding:2px 4px}
.stage-map{max-height:52vh;overflow:auto;padding-right:3px}.doc-preview{margin:.4rem 0 .7rem;border:1px solid var(--line);background:#f7fbfc}.doc-preview summary{cursor:pointer;padding:6px 9px;color:var(--blue);font-weight:700;font-size:.78rem}.doc-preview pre{margin:0;padding:10px 12px;border-top:1px solid var(--line);white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--ink)}
@media(max-width:850px){.stage-map{max-height:none;overflow:visible}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""


def validate(data: dict) -> None:
    if data.get("schema_version") != 1:
        raise ValueError("pipeline.json needs schema_version: 1")
    for key in ("stages", "events", "versions", "approvals"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"pipeline.json needs {key} as an array")
    project = data.get("project")
    if not isinstance(project, dict) or not project.get("name"):
        raise ValueError("pipeline.json needs project.name")
    ids = {}
    for key in ("stages", "events", "versions", "approvals"):
        found = set()
        for item in data[key]:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
                raise ValueError(f"every {key} item needs a nonempty string id")
            if item["id"] in found:
                raise ValueError(f"duplicate {key} id: {item['id']}")
            found.add(item["id"])
        ids[key] = found
    for stage in data["stages"]:
        status = stage.get("status")
        if status not in STAGE_LABELS:
            raise ValueError(f"unknown stage status: {status}")
        if status == "skipped" and not stage.get("skip_reason"):
            raise ValueError(f"skipped stage {stage['id']} needs skip_reason")
    if project.get("current_version_id") and project["current_version_id"] not in ids["versions"]:
        raise ValueError("project.current_version_id has no matching version")
    current = data.get("current")
    if current and not isinstance(current, dict):
        raise ValueError("current must be an object")
    if isinstance(current, dict) and current.get("stage_id") and current["stage_id"] not in ids["stages"]:
        raise ValueError("current.stage_id has no matching stage")
    for event in data["events"]:
        if not isinstance(event.get("title"), str) or not event["title"].strip():
            raise ValueError(f"event {event['id']} needs title")
        if event.get("type", "general") not in EVENT_LABELS:
            raise ValueError(f"unknown event type: {event.get('type')}")
        for field, collection in (("stage_id", "stages"), ("version_id", "versions"), ("corrects_event_id", "events")):
            if event.get(field) and event[field] not in ids[collection]:
                raise ValueError(f"event {event['id']} has unknown {field}: {event[field]}")
        if event.get("corrects_event_id") == event["id"]:
            raise ValueError(f"event {event['id']} cannot correct itself")
        questions = event.get("questions", [])
        if not isinstance(questions, list):
            raise ValueError(f"event {event['id']} questions must be an array")
        for question in questions:
            if not isinstance(question, dict):
                raise ValueError(f"event {event['id']} has invalid question")
            if question.get("status") and question["status"] not in QUESTION_LABELS:
                raise ValueError(f"unknown question status: {question['status']}")
    for approval in data["approvals"]:
        if approval.get("version_id") not in ids["versions"]:
            raise ValueError(f"approval {approval['id']} has unknown version_id")
        if approval.get("decision") not in DECISION_LABELS:
            raise ValueError(f"unknown approval decision: {approval.get('decision')}")
        if not approval.get("scope"):
            raise ValueError(f"approval {approval['id']} needs scope")
        if not isinstance(approval.get("evidence"), list):
            raise ValueError(f"approval {approval['id']} needs evidence array")


def render(data: dict, source_dir: Path, output_dir: Path) -> str:
    validate(data)
    project = data["project"]
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    dated, unknown = [], []
    for event in data["events"]:
        if not isinstance(event, dict):
            continue
        (dated if date_key(event.get("occurred_at")) else unknown).append(event)
    dated.sort(key=lambda e: date_key(e["occurred_at"]))
    unknown.sort(key=lambda e: date_key(e.get("recorded_at")) or datetime.max.replace(tzinfo=timezone.utc))
    approval_label, approval_explanation = approval_summary(data, source_dir, output_dir)
    stage_titles = {s["id"]: s.get("title") or s["id"] for s in data["stages"] if isinstance(s, dict) and s.get("id")}
    stages = "".join(stage_card(s, current.get("stage_id")) for s in data["stages"] if isinstance(s, dict)) or '<p class="muted">Этапы пока не описаны.</p>'
    dated_html = "".join(event_card(e, source_dir, output_dir, stage_titles) for e in dated) or '<p class="muted">Датированных событий пока нет.</p>'
    unknown_html = "".join(event_card(e, source_dir, output_dir, stage_titles) for e in unknown)
    unknown_section = f'<div class="unknown"><h3>Время события неизвестно</h3><p class="muted">Порядок здесь основан на времени записи, если оно есть.</p><div class="timeline">{unknown_html}</div></div>' if unknown else ""
    versions = "".join(f'<article class="version"><strong>{esc(v.get("label") or v.get("id") or "Версия")}</strong><span class="pill">{"Текущая" if v.get("id") == project.get("current_version_id") else "История"}</span><p>Объём: {esc(v.get("scope") or "Не указан")} · Создана: {show_date(v.get("created_at"))}</p>{artifacts(v.get("artifacts"), source_dir, output_dir)}</article>' for v in data["versions"] if isinstance(v, dict)) or '<p class="muted">Версии не зафиксированы.</p>'
    description = f'<p>{esc(project["description"])}</p>' if project.get("description") else ""
    next_step = esc(current.get("next_step") or "Следующий шаг не зафиксирован")
    current_summary = esc(current.get("summary") or "Текущее состояние не описано")
    blockers = text_list(current.get("blockers"), "Блокеры не зафиксированы")
    updated = show_date(data.get("updated_at"))
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>{esc(project["name"])} · Ход работы</title><style>{CSS}</style></head><body>
<div class="shell"><header class="hero"><div><div class="eyebrow">Business Skill Issue · история проекта</div><h1>{esc(project["name"])}</h1>{description}</div><div class="hero-aside"><span class="eyebrow">Сейчас</span><strong>{current_summary}</strong><p><b>Следующий шаг:</b> {next_step}</p><small>Обновлено: {updated}</small></div></header>
<nav class="toc" aria-label="Разделы"><a href="#stages">Этапы</a><a href="#timeline">Лента событий</a><a href="#versions">Версии</a><a href="#approvals">Согласования</a></nav>
<div class="layout"><main><section class="section" id="timeline"><div class="section-head"><h2>Лента событий</h2><p>Сверху вниз по времени события</p></div><div class="timeline">{dated_html}</div>{unknown_section}</section>
<section class="section" id="versions"><div class="section-head"><h2>Версии документов</h2><p>Точные снимки и их объём</p></div>{versions}</section>
<section class="section" id="approvals"><div class="section-head"><h2>Согласования</h2><p>Каждое решение привязано к версии</p></div><div class="approval-grid">{approval_cards(data, source_dir, output_dir)}</div></section></main>
<aside class="side"><div class="callout"><span class="eyebrow">Согласование текущей версии</span><h2>{esc(approval_label)}</h2><p>{esc(approval_explanation)}</p></div><section class="stage-map" id="stages"><h2>Карта этапов</h2><div class="stages">{stages}</div></section><div class="mini"><h3>Блокеры</h3>{blockers}</div></aside></div>
<footer class="footer">Локальный отчёт Business Skill Issue. События без времени вынесены отдельно; время записи не подменяет время события.</footer></div></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Input pipeline.json")
    parser.add_argument("--output", required=True, type=Path, help="Output standalone .html")
    args = parser.parse_args()
    source = args.input.resolve(strict=True)
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        parser.error("pipeline.json must contain one JSON object")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data, source.parent, output.parent), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
