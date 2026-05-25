import json
from pathlib import Path
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()
VLLM_BASE_URL = settings.VLLM_BASE_URL
VLLM_API_KEY = settings.VLLM_API_KEY
VLLM_MODEL = settings.VLLM_MODEL
OUTPUT_FILE = Path("judge_scores.json")



class LLMJudge:
    def __init__(self):
        if not settings.VLLM_API_KEY or not settings.VLLM_API_KEY.strip():
            raise RuntimeError("LLM Judge требует настроенный VLLM_API_KEY. Добавьте ключ в .env.")
        self.llm = ChatOpenAI(
            model=VLLM_MODEL,
            base_url=VLLM_BASE_URL,
            api_key=VLLM_API_KEY,
            temperature=0.0,
            max_tokens=7000
        )

    def build_prompt(self, trace: Dict[str, Any]) -> str:
        return f"""
Вы — объективный клинический аудитор качества медицинских заключений по КТ-измерениям аорты.
Ваша задача — оценить качество заключения строго по трём критериям.
Верните ТОЛЬКО валидный JSON без дополнительных пояснений.

Критерии оценивания:
   1. USEFULNESS (Полезность): Насколько итоговое заключение полезно кардиохирургу при принятии клинического решения по КТ-аорте?
   Содержит ли конкретные клинические выводы о диагнозе? Помогает ли определить дальнейшую тактику? Есть ли клинические рекомендации?
    Пример оценивания:
    Хорошо: "В предоставленных измерениях диаметр восходящей аорты 56 мм, что свидетельствует о значительном
    расширении этого отдела аорты и дилатации аорты. Показанием к хирургической коррекции восходящего отдела аорты
    считается аневризма диаметром 55 мм и более при отсутствии генетических дегенеративных заболеваний и двустворчатого аортального клапана."
    Плохо: "Есть изменения. Требуется наблюдение и консультация врача-кардиохирурга."
   Шкала: 1–3 бесполезно, 4–6 частично полезно, 7–8 клинически полезно, 9–10 готово к использованию.
   2. GROUNDEDNESS (Обоснованность): Насколько ответ строго основан на входных данных на входных измерениях JSON, анамнезе, предоставленном контексте?
   Есть ли галлюцинации или утверждения не подкрепленные данными?
   Ссылается ли логика заключения на предоставленный контекст?
    Пример оценивания:
    Хорошо: "Максимальный диаметр аорты 56 мм. Симптомов и жалоб у пациента нет. Согласно источнику 1, рекомендуется выполнять протезирование аорты
    бессимптомным пациентам с аневризмами корня и/или ВА при максимальном диаметре аорты более 5,5 см. Пациенту необходимо провести протезирование аорты"
    Плохо: "Максимальный диаметр аорты 45 мм. Пациенту необходимо провести протезирование аорты"
   Шкала: 1–3 сильная галлюцинации, 4–6 частичная опора на факты, 7–8 в целом обосновано, 9–10 строго обосновано.
   3. EFFICIENCY (Эффективность): Оптимальность траектории/использованных инструментов. Нет ли лишних шагов? Рационально ли используется поиск информации в базе знаний?
   Нет ли избыточных повторов операций или инструментов?
   Шкала: 1–3 крайне неэффективно, 4–6 средне, 7–8 эффективно, 9–10 оптимально.

Если данных для оценки критерия недостаточно, верните строку "недостаточно данных" вместо числа.
ОБЯЗАТЕЛЬНЫЙ ФОРМАТ ОТВЕТА (строго JSON):
{{
  "usefulness": <int 1-10 или "недостаточно данных">,
  "groundedness": <int 1-10 или "недостаточно данных">,
  "efficiency": <int 1-10 или "недостаточно данных">
}}

Данные для оценки (трассировка запроса к LLM):
{json.dumps(trace, ensure_ascii=False, indent=2)}
""".strip()

    def evaluate(self, trace: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.build_prompt(trace)
        response = self.llm.invoke(prompt)
        raw_text = response.content if hasattr(response, "content") else str(response)
        clean_text = raw_text.strip().lstrip("```json").rstrip("```").strip()

        try:
            result = json.loads(clean_text)
            expected_keys = {"usefulness", "groundedness", "efficiency"}
            if not expected_keys.issubset(result.keys()):
                raise ValueError("В ответе LLM отсутствуют обязательные ключи")
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"LLM Judge вернул невалидный JSON: {e}.")
            return {"usefulness": "ошибка парсинга", "groundedness": "ошибка парсинга", "efficiency": "ошибка парсинга"}
