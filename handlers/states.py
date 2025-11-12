"""FSM для опроса"""
from aiogram.fsm.state import State, StatesGroup


class SurveyFSM(StatesGroup):
    """Состояния опроса"""
    # Начальные вопросы
    Q1 = State()
    Q2 = State()
    
    # Языковые уточняющие вопросы
    LQ1 = State()
    LQ2 = State()
    LQ3 = State()
    LQ4 = State()
    LQ5 = State()
    
    # Ожидание текстового ввода
    waiting_input = State()
    
    # Показ рекомендаций
    showing_recommendations = State()
