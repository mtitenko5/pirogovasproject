from datetime import datetime, timezone
from html import escape
from typing import Any, Optional

from jinja2 import Template

DEFAULT_REPORT_TEMPLATE = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Отчет КТ аорты</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      font-size: 14px;
      line-height: 1.5;
      color: #111827;
      margin: 32px;
    }
    h1, h2 {
      margin: 0 0 12px;
    }
    h1 {
      font-size: 22px;
      border-bottom: 2px solid #111827;
      padding-bottom: 8px;
    }
    h2 {
      font-size: 17px;
      margin-top: 24px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
    }
    th, td {
      border: 1px solid #d1d5db;
      padding: 8px;
      vertical-align: top;
    }
    th {
      background: #f3f4f6;
      text-align: left;
    }
    .meta {
      margin-top: 16px;
    }
    .muted {
      color: #6b7280;
      font-size: 12px;
    }
    .section {
      margin-top: 18px;
    }
    pre {
      white-space: pre-wrap;
      font-family: Arial, sans-serif;
    }
    .ct-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      margin-top: 8px;
    }
    .ct-card img {
      width: 100%;
      max-height: 260px;
      object-fit: contain;
      border: 1px solid #d1d5db;
    }
  </style>
</head>
<body>
  <h1>Заключение врача-кардиохирурга по данным КТ</h1>

  <div class="meta">
    <table>
      <tr>
        <th>Пациент</th>
        <td>{{ meta.name }}</td>
      </tr>
      <tr>
        <th>Пол</th>
        <td>{{ meta.sex }}</td>
      </tr>
      <tr>
        <th>Дата рождения</th>
        <td>{{ meta.birth_date }}</td>
      </tr>
      <tr>
        <th>Дата КТ</th>
        <td>{{ meta.ct_date }}</td>
      </tr>
      <tr>
        <th>Анамнез</th>
        <td>{{ meta.anamnesis }}</td>
      </tr>
    </table>
  </div>

  <h2>Ключевые измерения</h2>
  <table>
    <thead>
      <tr>
        <th>Параметр</th>
        <th>Значение</th>
      </tr>
    </thead>
    <tbody>
      {% for item in measurements %}
      <tr>
        <td>{{ item.name }}</td>
        <td>{{ item.value }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <h2>Сформированное заключение</h2>
  <div class="section">
    <pre>{{ llm_response }}</pre>
  </div>

  {% if ct_images %}
  <h2>КТ-снимки</h2>
  <div class="ct-grid">
    {% for image in ct_images %}
    <div class="ct-card">
      <img src="{{ image.src }}" alt="{{ image.filename }}">
      <div class="muted">{{ image.filename }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if guideline_sources %}
  <h2>Источники клинических рекомендаций</h2>
  <ol>
    {% for source in guideline_sources %}
    <li>Гайдлайн {{ loop.index }} взят из файла {{ source }}</li>
    {% endfor %}
  </ol>
  {% endif %}

  <p class="muted">
    Отчет сформирован автоматически. Требуется проверка врачом.
    Дата формирования: {{ generated_at }}
  </p>
</body>
</html>
"""

def _as_dict(value: Any) -> dict:
    if isinstance(value,dict):
        return value
    return {}

FIELD_LABELS = {
    "Descending Aorta": "Нисходящая аорта",
    "Isthmus": "Перешеек аорты",
    "Arch after LSA": "Дуга аорты после левой подключичной артерии",
    "Arch after TBC": "Дуга аорты после плечеголовного ствола",
    "Ascending Aorta befor TBC": "Восходящая аорта перед плечеголовным стволом",
    "Ascending Aorta": "Восходящая аорта",
    "max_diam_1": "Максимальный диаметр 1",
    "max_diam_2": "Максимальный диаметр 2",
    "min_diam": "Минимальный диаметр",
    "perimetr": "Периметр",
    "area": "Площадь поперечного сечения",
}

SEX_LABELS = {
    "Male": "Мужской",
    "Female": "Женский",
}

def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, list):
        return ", ".join(_format_value(item) for item in value)
    return str(value)

def _flatten_measurements(data: dict, prefix: str = "") -> list[dict]:
    rows = []

    for key, value in data.items():
        title = FIELD_LABELS.get(key, key)
        full_title = f"{prefix} — {title}" if prefix else title

        if isinstance(value, dict):
            rows.extend(_flatten_measurements(value, full_title))
        else:
            rows.append({"name": full_title, "value": _format_value(value)})

    return rows

def _normalize_llm_response(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value,str):
        return value

    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            parts.append(f"{key}: {item}")
        return "\n\n".join(parts)
    
    return str(value)

def _extract_guideline_sources(report, meta: dict) -> list[str]:
    sources = meta.get("guideline_sources", [])
    if sources:
        return sources

    llm_response = getattr(report, "llm_response", None)
    if isinstance(llm_response, dict):
        return llm_response.get("guideline_sources", [])

    return []

def generate_html_report(
    report,
    template_content: Optional[str] = None,
    ct_images: Optional[list[dict]] = None,
) -> str:
    
    template = Template(template_content or DEFAULT_REPORT_TEMPLATE)

    meta = _as_dict(report.meta)
    meta["sex"] = SEX_LABELS.get(meta.get("sex"), meta.get("sex", ""))
    measurements = _flatten_measurements(_as_dict(report.measurements))
    guideline_sources = _extract_guideline_sources(report, meta)
    llm_response = _normalize_llm_response(report.llm_response)
    
    return template.render(
        meta=meta,
        measurements=measurements,
        llm_response = llm_response,
        ct_images=ct_images or [],
        guideline_sources=guideline_sources,
        report=report,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )
