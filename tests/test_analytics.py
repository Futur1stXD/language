"""Тесты для модуля аналитики"""
import pytest
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from models.database import Base
from models import Respondent, Answer
from services.analytics import SurveyAnalytics


# Фикстура для тестовой БД
@pytest.fixture
async def test_session():
    """Создать тестовую сессию БД"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    await engine.dispose()


@pytest.mark.asyncio
async def test_get_total_respondents_empty(test_session):
    """Тест: пустая БД возвращает 0 респондентов"""
    analytics = SurveyAnalytics(test_session)
    total = await analytics.get_total_respondents()
    assert total == 0


@pytest.mark.asyncio
async def test_get_total_respondents_with_data(test_session):
    """Тест: подсчёт респондентов с данными"""
    # Добавляем тестовых респондентов
    resp1 = Respondent(
        user_id=111,
        username="test1",
        language_code="ru",
        consented=True,
        completed=True,
        wave_id="wave_test"
    )
    resp2 = Respondent(
        user_id=222,
        username="test2",
        language_code="ru",
        consented=True,
        completed=True,
        wave_id="wave_test"
    )
    resp3 = Respondent(
        user_id=333,
        username="test3",
        language_code="ru",
        consented=True,
        completed=False,  # Не завершён
        wave_id="wave_test"
    )
    
    test_session.add_all([resp1, resp2, resp3])
    await test_session.commit()
    
    analytics = SurveyAnalytics(test_session)
    
    # Только завершённые
    total_completed = await analytics.get_total_respondents(completed_only=True)
    assert total_completed == 2
    
    # Все респонденты
    total_all = await analytics.get_total_respondents(completed_only=False)
    assert total_all == 3


@pytest.mark.asyncio
async def test_question_distribution(test_session):
    """Тест: распределение ответов на вопрос"""
    # Создаём респондентов
    resp1 = Respondent(user_id=111, consented=True, completed=True, wave_id="w1")
    resp2 = Respondent(user_id=222, consented=True, completed=True, wave_id="w1")
    resp3 = Respondent(user_id=333, consented=True, completed=True, wave_id="w1")
    
    test_session.add_all([resp1, resp2, resp3])
    await test_session.commit()
    await test_session.refresh(resp1)
    await test_session.refresh(resp2)
    await test_session.refresh(resp3)
    
    # Добавляем ответы на Q4
    answer1 = Answer(respondent_id=resp1.id, question_code="Q4", answer="Q4_OP2")
    answer2 = Answer(respondent_id=resp2.id, question_code="Q4", answer="Q4_OP2")
    answer3 = Answer(respondent_id=resp3.id, question_code="Q4", answer="Q4_OP3")
    
    test_session.add_all([answer1, answer2, answer3])
    await test_session.commit()
    
    analytics = SurveyAnalytics(test_session)
    dist = await analytics.get_question_distribution("Q4")
    
    assert dist == {"Q4_OP2": 2, "Q4_OP3": 1}


@pytest.mark.asyncio
async def test_multi_answer_distribution(test_session):
    """Тест: распределение для мультивыбора"""
    resp1 = Respondent(user_id=111, consented=True, completed=True, wave_id="w1")
    test_session.add(resp1)
    await test_session.commit()
    await test_session.refresh(resp1)
    
    # Мультиответ в JSON
    multi_answer = json.dumps(["Q9_OP1", "Q9_OP2", "Q9_OP3"])
    answer1 = Answer(respondent_id=resp1.id, question_code="Q9", answer=multi_answer)
    
    test_session.add(answer1)
    await test_session.commit()
    
    analytics = SurveyAnalytics(test_session)
    dist = await analytics.get_question_distribution("Q9")
    
    # Должны быть все 3 опции по 1 разу
    assert "Q9_OP1" in dist
    assert "Q9_OP2" in dist
    assert "Q9_OP3" in dist
    assert dist["Q9_OP1"] == 1


@pytest.mark.asyncio
async def test_export_csv_data(test_session):
    """Тест: экспорт данных в CSV формат"""
    resp1 = Respondent(
        user_id=111,
        consented=True,
        completed=True,
        wave_id="w1",
        completed_at=datetime(2025, 11, 11, 12, 0, 0)
    )
    test_session.add(resp1)
    await test_session.commit()
    await test_session.refresh(resp1)
    
    # Добавляем несколько ответов
    answer1 = Answer(respondent_id=resp1.id, question_code="Q1", answer="Q1_OP2")
    answer2 = Answer(respondent_id=resp1.id, question_code="Q4", answer="Q4_OP3")
    
    test_session.add_all([answer1, answer2])
    await test_session.commit()
    
    analytics = SurveyAnalytics(test_session)
    csv_data = await analytics.export_to_csv_data()
    
    assert len(csv_data) == 1
    assert csv_data[0]["user_id"] == 111
    assert csv_data[0]["wave_id"] == "w1"
    assert csv_data[0]["Q1"] == "Q1_OP2"
    assert csv_data[0]["Q4"] == "Q4_OP3"


@pytest.mark.asyncio
async def test_generate_stats_text_empty(test_session):
    """Тест: генерация статистики для пустой БД"""
    analytics = SurveyAnalytics(test_session)
    stats = await analytics.generate_stats_text()
    
    assert "Нет завершённых опросов" in stats


@pytest.mark.asyncio
async def test_open_answers(test_session):
    """Тест: получение открытых ответов"""
    resp1 = Respondent(user_id=111, consented=True, completed=True)
    resp2 = Respondent(user_id=222, consented=True, completed=True)
    
    test_session.add_all([resp1, resp2])
    await test_session.commit()
    await test_session.refresh(resp1)
    await test_session.refresh(resp2)
    
    answer1 = Answer(respondent_id=resp1.id, question_code="Q15", answer="Больше толерантности")
    answer2 = Answer(respondent_id=resp2.id, question_code="Q15", answer="Образовательные программы")
    
    test_session.add_all([answer1, answer2])
    await test_session.commit()
    
    analytics = SurveyAnalytics(test_session)
    open_answers = await analytics.get_open_answers("Q15")
    
    assert len(open_answers) == 2
    assert "Больше толерантности" in open_answers
    assert "Образовательные программы" in open_answers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
