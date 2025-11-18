from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from newapp.database import Database
from newapp.keyboards import Keyboards

router = Router()


@router.message(F.text.in_(["💰 Ставки", "💰 Betting"]))
async def cmd_betting(message: Message, db: Database):
    """Меню ставок"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = "💰 <b>Ставки на Polymarket</b>\n\nВыберите действие:"
    else:
        text = "💰 <b>Polymarket Betting</b>\n\nChoose an action:"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_betting_menu(language)
    )


@router.callback_query(F.data == "place_bet")
async def cb_place_bet(callback: CallbackQuery, db: Database):
    """Сделать ставку"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "🎯 <b>Сделать ставку</b>\n\nФункция в разработке. Скоро вы сможете делать ставки напрямую через бота!"
    else:
        text = "🎯 <b>Place Bet</b>\n\nFeature in development. Soon you'll be able to place bets directly through the bot!"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "available_markets")
async def cb_available_markets(callback: CallbackQuery, db: Database):
    """Доступные рынки"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "📊 <b>Доступные рынки</b>\n\n"
        text += "1. US Elections 2024 - $2.5M\n"
        text += "2. ETH ETF Approval - $1.8M\n"
        text += "3. Fed Rate Decision - $1.2M\n"
        text += "4. Bitcoin Halving - $950K\n"
        text += "5. Climate Events - $780K\n\n"
        text += "🔄 Данные обновляются каждые 5 минут"
    else:
        text = "📊 <b>Available Markets</b>\n\n"
        text += "1. US Elections 2024 - $2.5M\n"
        text += "2. ETH ETF Approval - $1.8M\n"
        text += "3. Fed Rate Decision - $1.2M\n"
        text += "4. Bitcoin Halving - $950K\n"
        text += "5. Climate Events - $780K\n\n"
        text += "🔄 Data updates every 5 minutes"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "bet_history")
async def cb_bet_history(callback: CallbackQuery, db: Database):
    """История ставок"""
    language = await db.get_user_language(callback.from_user.id)
    
    # Получаем историю ставок пользователя
    bets = await db.get_user_bets(callback.from_user.id, limit=5)
    
    if language == "ru":
        text = "📋 <b>История ставок</b>\n\n"
        if bets:
            for i, bet in enumerate(bets, 1):
                text += f"{i}. {bet['market_id'][:20]} - {bet['amount']} USDC - {bet['status']}\n"
        else:
            text += "У вас пока нет ставок."
    else:
        text = "📋 <b>Bet History</b>\n\n"
        if bets:
            for i, bet in enumerate(bets, 1):
                text += f"{i}. {bet['market_id'][:20]} - {bet['amount']} USDC - {bet['status']}\n"
        else:
            text += "You don't have any bets yet."
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "my_safe_wallet")
async def cb_my_safe_wallet(callback: CallbackQuery, db: Database):
    """Мой Safe кошелек"""
    language = await db.get_user_language(callback.from_user.id)
    
    # Получаем Safe кошелек пользователя
    safe_wallet = await db.get_user_safe_wallet(callback.from_user.id)
    
    if language == "ru":
        text = "🛡️ <b>Мой Safe кошелек</b>\n\n"
        if safe_wallet:
            text += f"Адрес: {safe_wallet['safe_address']}\n"
            text += f"Оригинальный: {safe_wallet['original_address']}\n"
            text += f"Статус: {'Активен' if safe_wallet['is_active'] else 'Неактивен'}"
        else:
            text += "У вас нет настроенного Safe кошелька.\n"
            text += "Для использования ставок необходимо настроить Safe кошелек."
    else:
        text = "🛡️ <b>My Safe Wallet</b>\n\n"
        if safe_wallet:
            text += f"Address: {safe_wallet['safe_address']}\n"
            text += f"Original: {safe_wallet['original_address']}\n"
            text += f"Status: {'Active' if safe_wallet['is_active'] else 'Inactive'}"
        else:
            text += "You don't have a Safe wallet configured.\n"
            text += "To use betting features, you need to set up a Safe wallet."
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()
