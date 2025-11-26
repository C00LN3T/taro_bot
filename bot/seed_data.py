from datetime import datetime
from typing import Iterable

from sqlmodel import select

from .models import NumerologyText, TarotCard, ZodiacSign


def tarot_seed() -> list[TarotCard]:
    majors = [
        TarotCard(name="Шут", arcana_type="major", suit=None, upright_meaning="Новый этап, свобода, любопытство", reversed_meaning="Импульсивность, наивность, неопределённость"),
        TarotCard(name="Маг", arcana_type="major", suit=None, upright_meaning="Инициатива, мастерство, контроль ситуации", reversed_meaning="Манипуляции, сомнения, неуверенность"),
        TarotCard(name="Верховная Жрица", arcana_type="major", suit=None, upright_meaning="Интуиция, тайна, мудрость", reversed_meaning="Секреты, отсутствие ясности, поверхностность"),
        TarotCard(name="Императрица", arcana_type="major", suit=None, upright_meaning="Изобилие, забота, созидание", reversed_meaning="Застой, зависимость, чрезмерная опека"),
        TarotCard(name="Император", arcana_type="major", suit=None, upright_meaning="Структура, власть, ответственность", reversed_meaning="Жёсткость, контроль, страх изменений"),
        TarotCard(name="Иерофант", arcana_type="major", suit=None, upright_meaning="Традиции, наставничество, духовный путь", reversed_meaning="Догматизм, консерватизм, упрямство"),
        TarotCard(name="Влюблённые", arcana_type="major", suit=None, upright_meaning="Выбор сердцем, союз, ценности", reversed_meaning="Сомнения, несогласие, разбалансировка"),
        TarotCard(name="Колесница", arcana_type="major", suit=None, upright_meaning="Прорыв, движение вперёд, воля", reversed_meaning="Растерянность, расфокус, конфликт целей"),
        TarotCard(name="Сила", arcana_type="major", suit=None, upright_meaning="Мужество, внутренний ресурс, сострадание", reversed_meaning="Неуверенность, подавление, нехватка энергии"),
        TarotCard(name="Отшельник", arcana_type="major", suit=None, upright_meaning="Поиск истины, мудрость, пауза", reversed_meaning="Изоляция, избегание, уход от ответственности"),
        TarotCard(name="Колесо Фортуны", arcana_type="major", suit=None, upright_meaning="Перемены, поворот событий, удача", reversed_meaning="Застой, повтор, упущенные возможности"),
        TarotCard(name="Справедливость", arcana_type="major", suit=None, upright_meaning="Баланс, честность, последствия", reversed_meaning="Несправедливость, дисбаланс, субъективность"),
        TarotCard(name="Повешенный", arcana_type="major", suit=None, upright_meaning="Новый взгляд, жертва ради смысла", reversed_meaning="Застрялость, нежелание менять перспективу"),
        TarotCard(name="Смерть", arcana_type="major", suit=None, upright_meaning="Завершение, трансформация, очищение", reversed_meaning="Сопротивление переменам, затяжные циклы"),
        TarotCard(name="Умеренность", arcana_type="major", suit=None, upright_meaning="Гармония, умеренность, интеграция", reversed_meaning="Крайности, нетерпение, дисбаланс"),
        TarotCard(name="Дьявол", arcana_type="major", suit=None, upright_meaning="Зависимости, искушение, сила желаний", reversed_meaning="Освобождение, осознание ограничений"),
        TarotCard(name="Башня", arcana_type="major", suit=None, upright_meaning="Внезапные перемены, освобождение", reversed_meaning="Страх перемен, удержание старого"),
        TarotCard(name="Звезда", arcana_type="major", suit=None, upright_meaning="Надежда, вдохновение, восстановление", reversed_meaning="Сомнения, потеря ориентира, усталость"),
        TarotCard(name="Луна", arcana_type="major", suit=None, upright_meaning="Интуиция, сны, скрытые процессы", reversed_meaning="Иллюзии, тревога, туманность"),
        TarotCard(name="Солнце", arcana_type="major", suit=None, upright_meaning="Оптимизм, успех, ясность", reversed_meaning="Отсутствие радости, временные трудности"),
        TarotCard(name="Суд", arcana_type="major", suit=None, upright_meaning="Пробуждение, ответственность, итог", reversed_meaning="Откладывание решений, самокритика"),
        TarotCard(name="Мир", arcana_type="major", suit=None, upright_meaning="Завершение, целостность, достижение", reversed_meaning="Незавершённость, незакрытые вопросы"),
    ]
    minors: list[TarotCard] = []
    ranks = [
        "Туз",
        "Двойка",
        "Тройка",
        "Четвёрка",
        "Пятёрка",
        "Шестёрка",
        "Семёрка",
        "Восьмёрка",
        "Девятка",
        "Десятка",
        "Паж",
        "Рыцарь",
        "Королева",
        "Король",
    ]
    suits = {
        "Жезлов": "энергия и действие",
        "Кубков": "эмоции и отношения",
        "Мечей": "мысли и решения",
        "Пентаклей": "материя и ресурсы",
    }
    for suit_name, theme in suits.items():
        for rank in ranks:
            minors.append(
                TarotCard(
                    name=f"{rank} {suit_name}",
                    arcana_type="minor",
                    suit=suit_name,
                    upright_meaning=f"{rank} {suit_name}: {theme} в прямом положении.",
                    reversed_meaning=f"{rank} {suit_name}: теневая сторона темы — сохраняйте баланс.",
                )
            )
    return majors + minors


def numerology_seed() -> list[NumerologyText]:
    descriptions = {
        1: "Лидерство, сила воли, инициативность.",
        2: "Дипломатия, гармония, поиск баланса.",
        3: "Коммуникация, творчество, лёгкость.",
        4: "Структура, стабильность, работа на результат.",
        5: "Свобода, перемены, гибкость.",
        6: "Забота, ответственность, семейные ценности.",
        7: "Глубина, анализ, духовный поиск.",
        8: "Материальный успех, амбиции, управление.",
        9: "Гуманизм, завершение циклов, служение обществу.",
    }
    results: list[NumerologyText] = []
    for number, desc in descriptions.items():
        for calc_type in ("destiny", "name", "life_cycle"):
            results.append(NumerologyText(number=number, type=calc_type, description=desc))
    return results


def zodiac_seed() -> list[ZodiacSign]:
    return [
        ZodiacSign(name="Козерог", date_start="12-22", date_end="01-19", description="Стратег, дисциплина, надёжность."),
        ZodiacSign(name="Водолей", date_start="01-20", date_end="02-18", description="Идеи, инновации, независимость."),
        ZodiacSign(name="Рыбы", date_start="02-19", date_end="03-20", description="Интуиция, эмпатия, мечтательность."),
        ZodiacSign(name="Овен", date_start="03-21", date_end="04-19", description="Энергия, решительность, действие."),
        ZodiacSign(name="Телец", date_start="04-20", date_end="05-20", description="Практичность, устойчивость, чувственность."),
        ZodiacSign(name="Близнецы", date_start="05-21", date_end="06-20", description="Коммуникация, адаптивность, любопытство."),
        ZodiacSign(name="Рак", date_start="06-21", date_end="07-22", description="Забота, глубина, дом и семья."),
        ZodiacSign(name="Лев", date_start="07-23", date_end="08-22", description="Лидерство, яркость, креативность."),
        ZodiacSign(name="Дева", date_start="08-23", date_end="09-22", description="Аналитика, порядок, полезность."),
        ZodiacSign(name="Весы", date_start="09-23", date_end="10-22", description="Баланс, красота, дипломатия."),
        ZodiacSign(name="Скорпион", date_start="10-23", date_end="11-21", description="Страсть, трансформация, глубина."),
        ZodiacSign(name="Стрелец", date_start="11-22", date_end="12-21", description="Свобода, смысл, исследования."),
    ]


def seed_timestamp() -> str:
    return datetime.utcnow().isoformat()


def ensure_seed(model_cls, session, data: Iterable) -> None:
    existing = session.exec(select(model_cls)).first()
    if existing:
        return
    session.add_all(list(data))
    session.commit()
