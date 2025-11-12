"""Модуль аналитики опроса"""
import json
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import Respondent, Answer


class SurveyAnalytics:
    """Класс для аналитики опроса"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_total_respondents(self, wave_id: str = None, completed_only: bool = True) -> int:
        """Получить общее количество респондентов"""
        query = select(func.count(Respondent.id)).where(
            Respondent.archived == False
        )
        
        if completed_only:
            query = query.where(Respondent.completed == True)
        
        if wave_id:
            query = query.where(Respondent.wave_id == wave_id)
        
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    async def get_question_distribution(self, question_code: str, wave_id: str = None) -> Dict[str, int]:
        """Получить распределение ответов на вопрос"""
        query = select(Answer.answer).join(Respondent).where(
            and_(
                Answer.question_code == question_code,
                Respondent.completed == True,
                Respondent.archived == False
            )
        )
        
        if wave_id:
            query = query.where(Respondent.wave_id == wave_id)
        
        result = await self.session.execute(query)
        answers = result.scalars().all()
        
        # Обрабатываем ответы (включая JSON для мультивыбора)
        processed = []
        for ans in answers:
            try:
                # Пробуем распарсить как JSON (мультивыбор)
                items = json.loads(ans)
                processed.extend(items)
            except:
                # Одиночный ответ
                processed.append(ans)
        
        return dict(Counter(processed))
    
    async def get_cross_tab(
        self, 
        question1: str, 
        question2: str, 
        wave_id: str = None
    ) -> Dict[Tuple[str, str], int]:
        """Построить кросс-таблицу для двух вопросов"""
        # Получаем всех завершённых респондентов
        query = select(Respondent.id).where(
            and_(
                Respondent.completed == True,
                Respondent.archived == False
            )
        )
        
        if wave_id:
            query = query.where(Respondent.wave_id == wave_id)
        
        result = await self.session.execute(query)
        respondent_ids = [r[0] for r in result.all()]
        
        # Получаем ответы на оба вопроса
        cross_data = defaultdict(int)
        
        for resp_id in respondent_ids:
            ans1_result = await self.session.execute(
                select(Answer.answer).where(
                    and_(
                        Answer.respondent_id == resp_id,
                        Answer.question_code == question1
                    )
                )
            )
            ans1 = ans1_result.scalar_one_or_none()
            
            ans2_result = await self.session.execute(
                select(Answer.answer).where(
                    and_(
                        Answer.respondent_id == resp_id,
                        Answer.question_code == question2
                    )
                )
            )
            ans2 = ans2_result.scalar_one_or_none()
            
            if ans1 and ans2:
                cross_data[(ans1, ans2)] += 1
        
        return dict(cross_data)
    
    async def get_open_answers(self, question_code: str, wave_id: str = None) -> List[str]:
        """Получить открытые ответы"""
        query = select(Answer.answer).join(Respondent).where(
            and_(
                Answer.question_code == question_code,
                Respondent.completed == True,
                Respondent.archived == False
            )
        )
        
        if wave_id:
            query = query.where(Respondent.wave_id == wave_id)
        
        result = await self.session.execute(query)
        return [ans for ans in result.scalars().all() if ans and ans.strip()]
    
    async def generate_stats_text(self, wave_id: str = None) -> str:
        """Сгенерировать текст статистики"""
        total = await self.get_total_respondents(wave_id)
        
        if total == 0:
            return "📊 Статистика\n\nНет завершённых опросов."
        
        text = f"📊 Статистика опроса\n\n"
        text += f"👥 Всего респондентов: {total}\n\n"
        
        # Q1: Проявления буллинга
        q1_dist = await self.get_question_distribution("Q1", wave_id)
        if q1_dist:
            text += "🤔 Проявления буллинга (Q1):\n"
            sorted_q1 = sorted(q1_dist.items(), key=lambda x: x[1], reverse=True)
            for code, count in sorted_q1[:3]:
                pct = (count / total) * 100
                label = self._get_option_label(code)
                text += f"  • {label}: {count} ({pct:.1f}%)\n"
            text += "\n"
        
        # Q2: Причины буллинга
        q2_dist = await self.get_question_distribution("Q2", wave_id)
        if q2_dist:
            text += "🔍 Причины буллинга (Q2):\n"
            sorted_q2 = sorted(q2_dist.items(), key=lambda x: x[1], reverse=True)
            for code, count in sorted_q2[:3]:
                pct = (count / total) * 100
                label = self._get_option_label(code)
                text += f"  • {label}: {count} ({pct:.1f}%)\n"
            text += "\n"
        
        # Q3: Инициатор буллинга
        q3_dist = await self.get_question_distribution("Q3", wave_id)
        if q3_dist:
            text += "Инициатор буллинга (Q3):\n"
            sorted_q3 = sorted(q3_dist.items(), key=lambda x: x[1], reverse=True)
            for code, count in sorted_q3:
                pct = (count / total) * 100
                label = self._get_option_label(code)
                text += f"  • {label}: {count} ({pct:.1f}%)\n"
            text += "\n"
        
        # Q5: Длительность буллинга
        q5_dist = await self.get_question_distribution("Q5", wave_id)
        if q5_dist:
            text += "🕐 Длительность буллинга (Q5):\n"
            sorted_q5 = sorted(q5_dist.items(), key=lambda x: x[1], reverse=True)
            for code, count in sorted_q5[:2]:
                pct = (count / total) * 100
                label = self._get_option_label(code)
                text += f"  • {label}: {count} ({pct:.1f}%)\n"
        
        return text
    
    async def generate_detailed_stats(self, wave_id: str = None) -> str:
        """Сгенерировать детальную статистику по всем вопросам"""
        total = await self.get_total_respondents(wave_id)
        
        if total == 0:
            return "📊 Детальная статистика\n\nНет завершённых опросов."
        
        text = f"📊 Детальная статистика по всем вопросам\n\n"
        text += f"👥 Всего респондентов: {total}\n"
        text += f"{'='*40}\n\n"
        
        # Определяем все вопросы
        question_titles = {
            # Первый этап (начальные вопросы)
            "Q1": "🤔 Проявления буллинга",
            "Q2": "Причины буллинга",
            "Q3": "Инициатор буллинга",
            "Q4": "Эмоции из-за буллинга",
            "Q5": "🕐 Длительность буллинга",
            "Q6": "Рассказывали ли о буллинге",
            
            # Второй этап (языковой буллинг)
            "LQ1": "Как происходит буллинг",
            "LQ2": "Прямые оскорбления",
            "LQ3": "⏰ Частота буллинга",
            "LQ4": "🛡 Реакция на буллинг",
            "LQ5": "Обстоятельства буллинга",
            "LQ6": "🌐 Язык конфликта",
            "LQ7": "💪 Попытки остановить буллинг",
            "LQ8": "🎯 Что больше всего задевает",
            "LQ9": "Поддержка окружающих",
            "LQ10": "📉 Влияние на жизнь",
        }
        
        # Список всех вопросов для итерации
        all_questions = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", 
                        "LQ1", "LQ2", "LQ3", "LQ4", "LQ5", 
                        "LQ6", "LQ7", "LQ8", "LQ9", "LQ10"]
        
        for q_code in all_questions:
            title = question_titles.get(q_code, q_code)
            text += f"{title}\n"
            
            # Получаем распределение ответов
            distribution = await self.get_question_distribution(q_code, wave_id)
            
            if not distribution:
                text += "  (Нет ответов)\n\n"
                continue
            
            # Сортируем по количеству (от большего к меньшему)
            sorted_dist = sorted(distribution.items(), key=lambda x: x[1], reverse=True)
            
            for code, count in sorted_dist:
                pct = (count / total) * 100
                label = self._get_option_label(code)
                text += f"  • {label}: {count} ({pct:.1f}%)\n"
            
            text += "\n"
        
        return text
    
    def _get_option_label(self, code: str) -> str:
        """Получить читаемое название опции"""
        labels = {
            # Q1 - Проявления буллинга
            "Q1_OP1": "Насмешки над речью (акцент, произношение)",
            "Q1_OP2": "Критика за язык",
            "Q1_OP3": "Требования говорить на другом языке",
            "Q1_OP4": "Насмешки над внешностью",
            "Q1_OP5": "Физическое насилие",
            "Q1_OP6": "Исключение из общения",
            "Q1_OP7": "Другое",
            
            # Q2 - Причины буллинга
            "Q2_OP1": "Акцент или произношение",
            "Q2_OP2": "Выбор языка общения",
            "Q2_OP3": "Незнание какого-то языка",
            "Q2_OP4": "Внешность",
            "Q2_OP5": "Поведение или характер",
            "Q2_OP6": "Материальное положение",
            "Q2_OP7": "Не знаю / Другое",
            
            # Q3 - Инициатор буллинга
            "Q3_OP1": "Один человек",
            "Q3_OP2": "Группа людей",
            "Q3_OP3": "Меняется",
            "Q3_OP4": "Затрудняюсь ответить",
            
            # Q4 - Эмоции
            "Q4_OP1": "Обида, грусть",
            "Q4_OP2": "Злость, раздражение",
            "Q4_OP3": "Страх, тревога",
            "Q4_OP4": "Стыд, смущение",
            "Q4_OP5": "Беспомощность",
            "Q4_OP6": "Одиночество",
            "Q4_OP7": "Другое",
            
            # Q5 - Длительность
            "Q5_OP1": "Недавно (менее месяца)",
            "Q5_OP2": "Несколько месяцев",
            "Q5_OP3": "Больше полугода",
            "Q5_OP4": "Больше года",
            "Q5_OP5": "Несколько лет",
            
            # Q6 - Рассказывали ли
            "Q6_OP1": "Да, близким",
            "Q6_OP2": "Да, специалистам",
            "Q6_OP3": "Рассказывал, не помогли",
            "Q6_OP4": "Нет, никому",
            "Q6_OP5": "Хочу, но не знаю кому",
            
            # LQ1 - Как происходит буллинг
            "LQ1_OP1": "Насмешка над акцентом",
            "LQ1_OP2": "Передразнивание речи",
            "LQ1_OP3": "Требования говорить по-другому",
            "LQ1_OP4": "Игнорирование",
            "LQ1_OP5": "Комментарии в интернете",
            "LQ1_OP6": "Другое",
            
            # LQ2 - Прямые оскорбления
            "LQ2_OP1": "Да, часто",
            "LQ2_OP2": "Иногда",
            "LQ2_OP3": "Нет, скрытая агрессия",
            "LQ2_OP4": "Нет оскорблений",
            
            # LQ3 - Частота
            "LQ3_OP1": "Каждый день",
            "LQ3_OP2": "Несколько раз в неделю",
            "LQ3_OP3": "Несколько раз в месяц",
            "LQ3_OP4": "Редко",
            
            # LQ4 - Реакция
            "LQ4_OP1": "Игнорирую",
            "LQ4_OP2": "Отвечаю, защищаюсь",
            "LQ4_OP3": "Перехожу на другой язык",
            "LQ4_OP4": "Ухожу, избегаю",
            "LQ4_OP5": "Чувствую плохо, ничего не делаю",
            "LQ4_OP6": "Другое",
            
            # LQ5 - Обстоятельства
            "LQ5_OP1": "В школе/учебном заведении",
            "LQ5_OP2": "В интернете",
            "LQ5_OP3": "В компании друзей",
            "LQ5_OP4": "В общественных местах",
            "LQ5_OP5": "Дома / в семье",
            "LQ5_OP6": "Другое",
            
            # LQ6 - Язык конфликта
            "LQ6_OP1": "Русский язык",
            "LQ6_OP2": "Украинский язык",
            "LQ6_OP3": "Английский язык",
            "LQ6_OP4": "Другой язык",
            "LQ6_OP5": "Не связано с языком",
            
            # LQ7 - Попытки остановить
            "LQ7_OP1": "Да, помогло",
            "LQ7_OP2": "Да, не помогло",
            "LQ7_OP3": "Да, стало хуже",
            "LQ7_OP4": "Нет, не знаю как",
            "LQ7_OP5": "Нет, боюсь",
            
            # LQ8 - Что задевает
            "LQ8_OP1": "Критика речи",
            "LQ8_OP2": "Непринятие языка",
            "LQ8_OP3": "Унижение культуры",
            "LQ8_OP4": "Публичность",
            "LQ8_OP5": "Постоянство",
            "LQ8_OP6": "Другое",
            
            # LQ9 - Поддержка
            "LQ9_OP1": "Да, поддерживают",
            "LQ9_OP2": "Частично",
            "LQ9_OP3": "Нет, одиноко",
            "LQ9_OP4": "Не знают о ситуации",
            
            # LQ10 - Влияние на жизнь
            "LQ10_OP1": "Не хочу общаться",
            "LQ10_OP2": "Боюсь говорить на языке",
            "LQ10_OP3": "Ухудшилась учеба/работа",
            "LQ10_OP4": "Проблемы со сном/аппетитом",
            "LQ10_OP5": "Тревога и стресс",
            "LQ10_OP6": "Низкая самооценка",
            "LQ10_OP7": "Почти не влияет",
            "LQ10_OP8": "Другое",
        }
        
        # Если код содержит дополнительный текст (например, "Q1_OP7:мой текст")
        if ":" in code:
            base_code, custom_text = code.split(":", 1)
            base_label = labels.get(base_code, base_code)
            return f"{base_label}: {custom_text}"
        
        return labels.get(code, code)
    
    async def export_to_csv_data(self, wave_id: str = None) -> List[Dict]:
        """Подготовить данные для экспорта в CSV"""
        query = select(Respondent).where(
            and_(
                Respondent.completed == True,
                Respondent.archived == False
            )
        )
        
        if wave_id:
            query = query.where(Respondent.wave_id == wave_id)
        
        result = await self.session.execute(query)
        respondents = result.scalars().all()
        
        csv_data = []
        
        for resp in respondents:
            row = {
                "user_id": resp.user_id,
                "wave_id": resp.wave_id,
                "completed_at": resp.completed_at.strftime("%Y-%m-%d %H:%M:%S") if resp.completed_at else "",
            }
            
            # Получаем все ответы респондента
            answers_result = await self.session.execute(
                select(Answer).where(Answer.respondent_id == resp.id)
            )
            answers = {a.question_code: a.answer for a in answers_result.scalars().all()}
            
            # Добавляем ответы по начальным вопросам (Q1-Q6)
            for i in range(1, 7):
                q_code = f"Q{i}"
                row[q_code] = answers.get(q_code, "")
            
            # Добавляем ответы по языковым вопросам (LQ1-LQ10)
            for i in range(1, 11):
                lq_code = f"LQ{i}"
                row[lq_code] = answers.get(lq_code, "")
            
            csv_data.append(row)
        
        return csv_data

