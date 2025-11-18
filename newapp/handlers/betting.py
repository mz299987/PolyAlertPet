from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Dict, Any
import logging

from newapp.builder_api import PolymarketBuilderAPI, BettingManager
from newapp.keyboards import Keyboards
from newapp.database import Database


class BettingStates(StatesGroup):
    """Состояния для процесса ставок"""
    waiting_for_market = State()
    waiting_for_outcome = State()
    waiting_for_amount = State()
    confirming_bet = State()


class BettingHandler:
    """Обработчик команд для ставок"""
    
    def __init__(self):
        self.router = Router()
        self.logger = logging.getLogger(__name__)
        self.setup_handlers()
    
    def setup_handlers(self):
        """Настройка обработчиков"""
        
        @self.router.message(Command("bet"))
        async def start_betting(message: Message, state: FSMContext, db, polymarket: PolymarketBuilderAPI):
            """Начало процесса ставки"""
            user_id = message.from_user.id
            
            # Проверяем, есть ли у пользователя кошельки
            wallets = await db.get_user_wallets(user_id)
            if not wallets:
                await message.answer(
                    "❌ У вас нет добавленных кошельков.\n"
                    "Сначала добавьте кошелек командой /add_wallet"
                )
                return
            
            # Создаем менеджер ставок
            betting_manager = BettingManager(polymarket, db)
            
            # Инициализируем систему ставок для первого кошелька
            wallet_address = wallets[0]['address']
            safe_address = await betting_manager.initialize_user_betting(user_id, wallet_address)
            
            if not safe_address:
                await message.answer(
                    "❌ Не удалось инициализировать систему ставок.\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
                return
            
            await state.update_data({
                'safe_address': safe_address,
                'wallet_address': wallet_address
            })
            
            await message.answer(
                f"🎯 <b>Размещение ставки</b>\n\n"
                f"🛡️ Ваш Safe кошелек: <code>{safe_address}</code>\n\n"
                f"📝 Введите ID рынка (market ID) для ставки:\n"
                f"<i>Пример: 0x1234...5678</i>"
            )
            await state.set_state(BettingStates.waiting_for_market)
        
        @self.router.message(BettingStates.waiting_for_market)
        async def process_market_id(message: Message, state: FSMContext):
            """Обработка ID рынка"""
            market_id = message.text.strip()
            
            # Базовая валидация market ID
            if not market_id.startswith("0x") or len(market_id) != 42:
                await message.answer(
                    "❌ Неверный формат Market ID.\n"
                    "Должен быть в формате 0x... (42 символа)\n\n"
                    "Попробуйте еще раз:"
                )
                return
            
            # Получаем информацию о рынке
            # Временная заглушка - нужно интегрировать с реальным API
            market_info = {
                "title": "Sample Market",
                "outcomes": ["Да", "Нет"]
            }
            
            await state.update_data({
                'market_id': market_id,
                'market_title': market_info['title'],
                'outcomes': market_info['outcomes']
            })
            
            outcomes_text = "\n".join([f"{i+1}. {outcome}" for i, outcome in enumerate(market_info['outcomes'])])
            
            await message.answer(
                f"📊 <b>Рынок:</b> {market_info['title']}\n\n"
                f"🎯 <b>Выберите исход:</b>\n"
                f"{outcomes_text}\n\n"
                f"Введите номер исхода (1-{len(market_info['outcomes'])}):"
            )
            await state.set_state(BettingStates.waiting_for_outcome)
        
        @self.router.message(BettingStates.waiting_for_outcome)
        async def process_outcome(message: Message, state: FSMContext):
            """Обработка выбора исхода"""
            try:
                outcome_num = int(message.text.strip())
                data = await state.get_data()
                outcomes = data.get('outcomes', [])
                
                if outcome_num < 1 or outcome_num > len(outcomes):
                    await message.answer(
                        f"❌ Неверный номер исхода.\n"
                        f"Введите число от 1 до {len(outcomes)}:"
                    )
                    return
                
                outcome_index = outcome_num - 1
                selected_outcome = outcomes[outcome_index]
                
                await state.update_data({
                    'outcome': outcome_index,
                    'selected_outcome': selected_outcome
                })
                
                await message.answer(
                    f"✅ <b>Выбран исход:</b> {selected_outcome}\n\n"
                    f"💵 <b>Введите сумму ставки в USDC:</b>\n"
                    f"<i>Пример: 10.5</i>"
                )
                await state.set_state(BettingStates.waiting_for_amount)
                
            except ValueError:
                await message.answer(
                    "❌ Пожалуйста, введите число.\n"
                    "Попробуйте еще раз:"
                )
        
        @self.router.message(BettingStates.waiting_for_amount)
        async def process_amount(message: Message, state: FSMContext):
            """Обработка суммы ставки"""
            try:
                amount = float(message.text.strip())
                
                if amount <= 0:
                    await message.answer(
                        "❌ Сумма должна быть больше 0.\n"
                        "Попробуйте еще раз:"
                    )
                    return
                
                if amount > 1000:  # Лимит на ставку
                    await message.answer(
                        "❌ Максимальная сумма ставки - 1000 USDC.\n"
                        "Попробуйте еще раз:"
                    )
                    return
                
                data = await state.get_data()
                
                await state.update_data({
                    'amount': amount
                })
                
                bet_summary = (
                    f"🎯 <b>Сводка ставки</b>\n\n"
                    f"📊 <b>Рынок:</b> {data['market_title']}\n"
                    f"🎯 <b>Исход:</b> {data['selected_outcome']}\n"
                    f"💵 <b>Сумма:</b> {amount} USDC\n"
                    f"🛡️ <b>Кошелек:</b> <code>{data['safe_address'][:10]}...{data['safe_address'][-8:]}</code>\n\n"
                    f"✅ <b>Подтвердить ставку?</b>\n"
                    f"Отправьте 'да' для подтверждения или 'нет' для отмены."
                )
                
                await message.answer(bet_summary)
                await state.set_state(BettingStates.confirming_bet)
                
            except ValueError:
                await message.answer(
                    "❌ Пожалуйста, введите число.\n"
                    "Попробуйте еще раз:"
                )
        
        @self.router.message(BettingStates.confirming_bet)
        async def confirm_bet(message: Message, state: FSMContext, db, polymarket: PolymarketBuilderAPI):
            """Подтверждение ставки"""
            user_id = message.from_user.id
            confirmation = message.text.strip().lower()
            
            if confirmation not in ['да', 'нет', 'yes', 'no']:
                await message.answer(
                    "❌ Пожалуйста, ответьте 'да' или 'нет'.\n"
                    "Подтвердите ставку:"
                )
                return
            
            if confirmation in ['нет', 'no']:
                await message.answer("❌ Ставка отменена.")
                await state.clear()
                return
            
            # Размещаем ставку
            data = await state.get_data()
            betting_manager = BettingManager(polymarket, db)
            
            await message.answer("⏳ Размещаем ставку...")
            
            tx_hash = await betting_manager.place_bet_for_user(
                user_id, 
                data['market_id'], 
                data['outcome'], 
                data['amount']
            )
            
            if tx_hash:
                await message.answer(
                    f"✅ <b>Ставка размещена!</b>\n\n"
                    f"📊 <b>Рынок:</b> {data['market_title']}\n"
                    f"🎯 <b>Исход:</b> {data['selected_outcome']}\n"
                    f"💵 <b>Сумма:</b> {data['amount']} USDC\n"
                    f"🔗 <b>Транзакция:</b> <code>{tx_hash}</code>\n\n"
                    f"Можете отслеживать статус в истории ставок /my_bets"
                )
            else:
                await message.answer(
                    "❌ <b>Ошибка при размещении ставки</b>\n\n"
                    "Попробуйте позже или обратитесь в поддержку."
                )
            
            await state.clear()
        
        @self.router.message(Command("my_bets"))
        async def show_bet_history(message: Message, db):
            """Показывает историю ставок пользователя"""
            user_id = message.from_user.id
            
            bets = await db.get_user_bets(user_id, limit=10)
            
            if not bets:
                await message.answer("📭 У вас еще нет ставок.")
                return
            
            bets_text = "📋 <b>Ваши последние ставки:</b>\n\n"
            
            for i, bet in enumerate(bets, 1):
                status_emoji = "✅" if bet['status'] == 'confirmed' else "⏳"
                bets_text += (
                    f"{i}. {status_emoji} <b>{bet['market_id'][:10]}...</b>\n"
                    f"   Исход: {bet['outcome']} | Сумма: {bet['amount']} USDC\n"
                    f"   Статус: {bet['status']}\n\n"
                )
            
            await message.answer(bets_text)
        
        @self.router.message(Command("markets"))
        async def show_available_markets(message: Message, polymarket: PolymarketBuilderAPI):
            """Показывает доступные рынки"""
            # Временная заглушка - нужно интегрировать с реальным API
            sample_markets = [
                {
                    "id": "0x1234567890abcdef1234567890abcdef12345678",
                    "title": "Будет ли цена BTC выше $50,000 к концу года?",
                    "liquidity": 15000.0
                },
                {
                    "id": "0xabcdef1234567890abcdef1234567890abcdef12", 
                    "title": "Выиграет ли Team A в следующем матче?",
                    "liquidity": 8000.0
                }
            ]
            
            markets_text = "📊 <b>Доступные рынки:</b>\n\n"
            
            for market in sample_markets:
                markets_text += (
                    f"🔹 <b>{market['title']}</b>\n"
                    f"   ID: <code>{market['id']}</code>\n"
                    f"   Ликвидность: {market['liquidity']} USDC\n\n"
                )
            
            markets_text += "💡 Для ставки используйте команду /bet"
            
            await message.answer(markets_text)


        # Обработчики для интерактивных кнопок
        @self.router.message(F.text.contains("💰 Ставки") | F.text.contains("💰 Betting"))
        async def show_betting_menu(message: Message, db):
            """Показывает меню ставок"""
            user_id = message.from_user.id
            language = await db.get_user_language(user_id)
            
            keyboard = Keyboards.get_betting_menu(language)
            
            if language == "ru":
                text = "🎯 <b>Меню ставок</b>\n\nВыберите действие:"
            else:
                text = "🎯 <b>Betting Menu</b>\n\nChoose an action:"
            
            await message.answer(text, reply_markup=keyboard)
        
        @self.router.message(F.text.contains("🎯 Мои ставки") | F.text.contains("🎯 My Bets"))
        async def show_my_bets(message: Message, db):
            """Показывает историю ставок"""
            user_id = message.from_user.id
            bets = await db.get_user_bets(user_id, limit=10)
            
            if not bets:
                await message.answer("📭 У вас еще нет ставок.")
                return
            
            bets_text = "📋 <b>Ваши последние ставки:</b>\n\n"
            
            for i, bet in enumerate(bets, 1):
                status_emoji = "✅" if bet['status'] == 'confirmed' else "⏳"
                bets_text += (
                    f"{i}. {status_emoji} <b>{bet['market_id'][:10]}...</b>\n"
                    f"   Исход: {bet['outcome']} | Сумма: {bet['amount']} USDC\n"
                    f"   Статус: {bet['status']}\n\n"
                )
            
            await message.answer(bets_text)
        
        @self.router.callback_query(F.data == "place_bet")
        async def start_betting_callback(callback: CallbackQuery, state: FSMContext, db, polymarket: PolymarketBuilderAPI):
            """Начинает процесс ставки через кнопку"""
            user_id = callback.from_user.id
            
            # Проверяем, есть ли у пользователя кошельки
            wallets = await db.get_user_wallets(user_id)
            if not wallets:
                await callback.answer("❌ Сначала добавьте кошелек", show_alert=True)
                return
            
            # Создаем менеджер ставок
            betting_manager = BettingManager(polymarket, db)
            
            # Инициализируем систему ставок для первого кошелька
            wallet_address = wallets[0]['address']
            safe_address = await betting_manager.initialize_user_betting(user_id, wallet_address)
            
            if not safe_address:
                await callback.answer("❌ Ошибка инициализации", show_alert=True)
                return
            
            await state.update_data({
                'safe_address': safe_address,
                'wallet_address': wallet_address
            })
            
            language = await db.get_user_language(user_id)
            
            if language == "ru":
                text = (
                    f"🎯 <b>Размещение ставки</b>\n\n"
                    f"🛡️ Ваш Safe кошелек: <code>{safe_address}</code>\n\n"
                    f"📝 Введите ID рынка (market ID) для ставки:\n"
                    f"<i>Пример: 0x1234...5678</i>"
                )
            else:
                text = (
                    f"🎯 <b>Placing Bet</b>\n\n"
                    f"🛡️ Your Safe wallet: <code>{safe_address}</code>\n\n"
                    f"📝 Enter market ID for betting:\n"
                    f"<i>Example: 0x1234...5678</i>"
                )
            
            await callback.message.edit_text(text)
            await state.set_state(BettingStates.waiting_for_market)
            await callback.answer()
        
        @self.router.callback_query(F.data == "available_markets")
        async def show_available_markets_callback(callback: CallbackQuery, polymarket: PolymarketBuilderAPI):
            """Показывает доступные рынки"""
            # Временная заглушка
            sample_markets = [
                {
                    "id": "0x1234567890abcdef1234567890abcdef12345678",
                    "title": "Будет ли цена BTC выше $50,000 к концу года?",
                    "liquidity": 15000.0
                },
                {
                    "id": "0xabcdef1234567890abcdef1234567890abcdef12", 
                    "title": "Выиграет ли Team A в следующем матче?",
                    "liquidity": 8000.0
                }
            ]
            
            markets_text = "📊 <b>Доступные рынки:</b>\n\n"
            
            for market in sample_markets:
                markets_text += (
                    f"🔹 <b>{market['title']}</b>\n"
                    f"   ID: <code>{market['id']}</code>\n"
                    f"   Ликвидность: {market['liquidity']} USDC\n\n"
                )
            
            markets_text += "💡 Для ставки нажмите \"Сделать ставку\""
            
            await callback.message.edit_text(markets_text)
            await callback.answer()
        
        @self.router.callback_query(F.data == "bet_history")
        async def show_bet_history_callback(callback: CallbackQuery, db):
            """Показывает историю ставок"""
            user_id = callback.from_user.id
            bets = await db.get_user_bets(user_id, limit=10)
            
            if not bets:
                await callback.message.edit_text("📭 У вас еще нет ставок.")
                await callback.answer()
                return
            
            bets_text = "📋 <b>Ваши последние ставки:</b>\n\n"
            
            for i, bet in enumerate(bets, 1):
                status_emoji = "✅" if bet['status'] == 'confirmed' else "⏳"
                bets_text += (
                    f"{i}. {status_emoji} <b>{bet['market_id'][:10]}...</b>\n"
                    f"   Исход: {bet['outcome']} | Сумма: {bet['amount']} USDC\n"
                    f"   Статус: {bet['status']}\n\n"
                )
            
            await callback.message.edit_text(bets_text)
            await callback.answer()


# Создаем экземпляр роутера
betting_handler = BettingHandler()
router = betting_handler.router

# Новые обработчики
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
