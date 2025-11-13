from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app import core
from app.db import ensure_user, get_user_lang, set_user_lang
from app.keyboards import language_inline_keyboard, main_menu_keyboard, get_main_text

dp = core.dp


@dp.message(Command("start"))
async def cmd_start(message: Message):
    assert core.db_pool is not None
    await ensure_user(core.db_pool, message.from_user.id)

    lang = await get_user_lang(core.db_pool, message.from_user.id)

    if not lang:
        await message.answer(
            "Choose your language / Выберите язык",
            reply_markup=language_inline_keyboard(),
        )
        return

    text = get_main_text(lang)
    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@dp.callback_query(F.data.startswith("set_lang:"))
async def cb_set_lang(callback: CallbackQuery):
    assert core.db_pool is not None
    lang = callback.data.split(":", 1)[1]
    if lang not in ("en", "ru"):
        await callback.answer()
        return

    await set_user_lang(core.db_pool, callback.from_user.id, lang)
    text = get_main_text(lang)
    kb = main_menu_keyboard(lang)

    try:
        await callback.message.edit_text(
            "✅ Language set" if lang == "en" else "✅ Язык сохранён"
        )
    except Exception:
        pass

    await core.bot.send_message(  # type: ignore[arg-type]
        callback.message.chat.id,
        text,
        reply_markup=kb,
    )
    await callback.answer("OK")


@dp.message(F.text.in_(["⬅ Back", "⬅ Назад"]))
async def btn_back(message: Message):
    assert core.db_pool is not None
    lang = await get_user_lang(core.db_pool, message.from_user.id)
    text = get_main_text(lang)
    await message.answer(text, reply_markup=main_menu_keyboard(lang))
