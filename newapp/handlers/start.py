from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery

from newapp.database import Database
from newapp.keyboards import Keyboards

router = Router()


@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start(message: Message, db: Database):
    """Обработка команды /start"""
    await db.ensure_user(message.from_user.id)
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = (
            "👋 Добро пожаловать в Polymarket Tracker!\n\n"
            "Я помогу вам отслеживать ваши позиции на Polymarket.\n"
            "Что я умею:\n"
            "• Показывать состояние портфеля\n"
            "• Отслеживать прибыль/убытки\n"
            "• Показывать активные события\n\n"
            "Используйте кнопки ниже для навигации."
        )
    else:
        text = (
            "👋 Welcome to Polymarket Tracker!\n\n"
            "I'll help you track your positions on Polymarket.\n"
            "What I can do:\n"
            "• Show portfolio status\n"
            "• Track profit/loss\n"
            "• Show active events\n\n"
            "Use the buttons below to navigate."
        )
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_main_menu(language)
    )


@router.message(F.text.in_(["⬅️ Назад", "⬅️ Back"]))
async def cmd_back(message: Message, db: Database):
    """Обработка кнопки Назад"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = "Главное меню"
    else:
        text = "Main menu"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_main_menu(language)
    )


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(callback: CallbackQuery, db: Database):
    """Обработка кнопки Назад из инлайн-клавиатуры"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "Главное меню"
    else:
        text = "Main menu"
    
    await callback.message.edit_text(
        text,
        reply_markup=None
    )
    
    await callback.message.answer(
        text,
        reply_markup=Keyboards.get_main_menu(language)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang_"))
async def cb_set_language(callback: CallbackQuery, db: Database):
    """Обработка выбора языка"""
    language = callback.data.split("_")[1]
    await db.set_user_language(callback.from_user.id, language)
    
    if language == "ru":
        text = "✅ Язык изменен на русский"
    else:
        text = "✅ Language changed to English"
    
    await callback.message.edit_text(text)
    await callback.answer(text)