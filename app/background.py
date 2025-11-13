import asyncio

from app import core
from app.polymarket import pm_get_positions, pm_get_value, pm_get_activity_trades


async def monitor_positions():
    assert core.db_pool is not None
    assert core.config is not None

    while True:
        try:
            async with core.db_pool.acquire() as conn:
                wallets = await conn.fetch(
                    """
                    SELECT w.id, w.address, w.tg_user_id, w.label
                    FROM wallets w
                    WHERE w.is_whale=FALSE AND w.alerts_enabled=TRUE
                    """
                )

            for w in wallets:
                address = w["address"]
                wallet_id = w["id"]
                tg_id = w["tg_user_id"]
                label = w["label"]

                try:
                    positions = await pm_get_positions(address)
                except Exception:
                    continue

                try:
                    total_value = await pm_get_value(address)
                except Exception:
                    total_value = None

                if total_value is not None:
                    async with core.db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO equity_snapshots (wallet_id, taken_at, total_value)
                            VALUES ($1, $2, $3)
                            """,
                            wallet_id,
                            core.now_utc(),
                            total_value,
                        )

                async with core.db_pool.acquire() as conn:
                    for p in positions:
                        cond_id = p.get("conditionId")
                        title = p.get("title")
                        outcome = p.get("outcome")
                        cur_pct = p.get("percentPnl")
                        cur_price = p.get("curPrice")

                        if cond_id is None or cur_pct is None:
                            continue

                        row = await conn.fetchrow(
                            """
                            SELECT last_percent_pnl
                            FROM position_snapshots
                            WHERE wallet_id=$1 AND condition_id=$2
                            """,
                            wallet_id,
                            cond_id,
                        )
                        should_alert = False
                        if row is None:
                            should_alert = False
                        else:
                            prev_pct = row["last_percent_pnl"]
                            if prev_pct is not None:
                                delta = float(cur_pct) - float(prev_pct)
                                if abs(delta) >= core.config.alert_threshold_percent:
                                    should_alert = True

                        await conn.execute(
                            """
                            INSERT INTO position_snapshots (
                                wallet_id, condition_id, title, outcome,
                                last_percent_pnl, last_cur_price, last_alert_at, updated_at
                            )
                            VALUES ($1, $2, $3, $4, $5, $6,
                                    CASE WHEN $7 THEN now() ELSE last_alert_at END,
                                    now())
                            ON CONFLICT (wallet_id, condition_id)
                            DO UPDATE SET
                                title=EXCLUDED.title,
                                outcome=EXCLUDED.outcome,
                                last_percent_pnl=EXCLUDED.last_percent_pnl,
                                last_cur_price=EXCLUDED.last_cur_price,
                                last_alert_at=CASE
                                    WHEN $7 THEN now()
                                    ELSE position_snapshots.last_alert_at
                                END,
                                updated_at=now()
                            """,
                            wallet_id,
                            cond_id,
                            title,
                            outcome,
                            float(cur_pct),
                            float(cur_price) if cur_price is not None else None,
                            should_alert,
                        )

                        if should_alert and core.bot is not None:
                            label_text = f" ({label})" if label else ""
                            sign = "+" if float(cur_pct) >= 0 else ""
                            text = (
                                "⚠️ Движение по позиции\n\n"
                                f"Кошелёк: <code>{address}</code>{label_text}\n"
                                f"Рынок: <b>{title}</b>\n"
                                f"Исход: <code>{outcome}</code>\n"
                                f"Текущий PnL: {sign}{float(cur_pct):.2f}%\n"
                            )
                            try:
                                await core.bot.send_message(  # type: ignore[arg-type]
                                    tg_id,
                                    text,
                                    parse_mode="HTML",
                                )
                            except Exception:
                                pass

        except Exception:
            pass

        await asyncio.sleep(core.config.poll_interval_seconds)


async def monitor_whales():
    assert core.db_pool is not None
    assert core.config is not None

    while True:
        try:
            async with core.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT w.id, w.address, w.label, w.tg_user_id,
                           COALESCE(am.last_seen_timestamp, 0) as last_ts,
                           am.id as marker_id
                    FROM wallets w
                    LEFT JOIN activity_markers am ON am.wallet_id = w.id
                    WHERE w.is_whale=TRUE AND w.whale_alerts_enabled=TRUE
                    """
                )

            for r in rows:
                wallet_id = r["id"]
                address = r["address"]
                label = r["label"]
                tg_id = r["tg_user_id"]
                last_ts = int(r["last_ts"] or 0)
                marker_id = r["marker_id"]

                try:
                    trades = await pm_get_activity_trades(address, since_ts=last_ts)
                except Exception:
                    continue

                if not trades:
                    continue

                trades_sorted = sorted(trades, key=lambda t: int(t.get("timestamp", 0)))
                max_ts = last_ts

                for t in trades_sorted:
                    ts = int(t.get("timestamp", 0))
                    if ts <= last_ts:
                        continue
                    max_ts = max(max_ts, ts)

                    title = t.get("title")
                    outcome = t.get("outcome")
                    side = t.get("side")
                    usdc_size = t.get("usdcSize")
                    price = t.get("price")
                    slug = t.get("slug")
                    event_slug = t.get("eventSlug")

                    label_text = f" ({label})" if label else ""
                    url = (
                        f"https://polymarket.com/event/{event_slug}/{slug}"
                        if slug and event_slug
                        else ""
                    )

                    text_lines = [
                        "🐳 Новая сделка кита",
                        f"Кошелёк: <code>{address}</code>{label_text}",
                        f"Рынок: <b>{title}</b>",
                        f"Сторона: <b>{side}</b> по исходу <code>{outcome}</code>",
                    ]
                    if usdc_size is not None:
                        try:
                            usdc_f = float(usdc_size)
                            text_lines.append(f"Объём: <b>{usdc_f:.2f} USDC</b>")
                        except Exception:
                            pass
                    if price is not None:
                        try:
                            price_f = float(price)
                            text_lines.append(f"Цена: {price_f:.3f}")
                        except Exception:
                            pass
                    if url:
                        text_lines.append(f"\n<a href=\"{url}\">Открыть рынок</a>")

                    if core.bot is not None:
                        try:
                            await core.bot.send_message(  # type: ignore[arg-type]
                                tg_id,
                                "\n".join(text_lines),
                                parse_mode="HTML",
                                disable_web_page_preview=True,
                            )
                        except Exception:
                            pass

                if max_ts > last_ts:
                    async with core.db_pool.acquire() as conn:
                        if marker_id:
                            await conn.execute(
                                "UPDATE activity_markers SET last_seen_timestamp=$1 WHERE id=$2",
                                max_ts,
                                marker_id,
                            )
                        else:
                            await conn.execute(
                                "INSERT INTO activity_markers (wallet_id, last_seen_timestamp) VALUES ($1, $2)",
                                wallet_id,
                                max_ts,
                            )

        except Exception:
            pass

        await asyncio.sleep(core.config.whale_poll_interval_seconds)
