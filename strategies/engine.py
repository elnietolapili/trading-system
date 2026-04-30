"""
Motor de backtest: evalúa reglas de estrategia contra datos OHLCV.

Operadores disponibles para reglas:
    crosses_above    - indicador cruza por encima de otro indicador o valor
    crosses_below    - indicador cruza por debajo de otro indicador o valor
    greater_than     - indicador mayor que valor o indicador
    less_than        - indicador menor que valor o indicador
    sar_below_price  - SAR está por debajo del precio (alcista)
    sar_above_price  - SAR está por encima del precio (bajista)
"""


def get_value(row, field):
    """Obtiene un valor de la fila: puede ser un nombre de columna o un número."""
    if isinstance(field, (int, float)):
        return float(field)
    if isinstance(field, str):
        try:
            return float(field)
        except ValueError:
            return row.get(field)
    return None


def eval_condition(row, prev_row, condition):
    """Evalúa una condición individual contra una fila y su anterior."""
    indicator = condition.get("indicator")
    operator = condition.get("operator")
    value = condition.get("value")

    curr_val = get_value(row, indicator)
    target_val = get_value(row, value)

    if curr_val is None or target_val is None:
        return False

    if operator == "greater_than":
        return curr_val > target_val

    elif operator == "less_than":
        return curr_val < target_val

    elif operator == "crosses_above":
        if prev_row is None:
            return False
        prev_val = get_value(prev_row, indicator)
        prev_target = get_value(prev_row, value)
        if prev_val is None or prev_target is None:
            return False
        return prev_val <= prev_target and curr_val > target_val

    elif operator == "crosses_below":
        if prev_row is None:
            return False
        prev_val = get_value(prev_row, indicator)
        prev_target = get_value(prev_row, value)
        if prev_val is None or prev_target is None:
            return False
        return prev_val >= prev_target and curr_val < target_val

    elif operator == "sar_below_price":
        sar_val = get_value(row, indicator)
        return sar_val is not None and sar_val < row.get("close", 0)

    elif operator == "sar_above_price":
        sar_val = get_value(row, indicator)
        return sar_val is not None and sar_val > row.get("close", 0)

    return False


def eval_rules(row, prev_row, rules):
    """Evalúa una lista de reglas (AND). Todas deben cumplirse."""
    if not rules:
        return False
    return all(eval_condition(row, prev_row, r) for r in rules)


def run_backtest(candles, entry_rules, exit_rules, stop_loss_pct=None,
                 take_profit_pct=None, position_size=100):
    """
    Ejecuta backtest sobre una lista de velas.

    Args:
        candles: lista de dicts con OHLCV + indicadores
        entry_rules: lista de condiciones de entrada
        exit_rules: lista de condiciones de salida
        stop_loss_pct: % de stop loss (ej: 2.0)
        take_profit_pct: % de take profit (ej: 5.0)
        position_size: tamaño de posición en USD

    Returns:
        dict con trades, métricas y equity curve
    """
    trades = []
    equity_curve = []
    position = None  # None = sin posición, dict = posición abierta
    balance = position_size

    for i, row in enumerate(candles):
        prev_row = candles[i - 1] if i > 0 else None
        close = row.get("close")
        time = row.get("time")

        if close is None:
            continue

        # ── Sin posición: buscar entrada ──
        if position is None:
            if eval_rules(row, prev_row, entry_rules):
                quantity = balance / close
                position = {
                    "entry_time": time,
                    "entry_price": close,
                    "quantity": quantity,
                    "cost": balance,
                }

        # ── Con posición: buscar salida ──
        else:
            should_exit = False
            exit_reason = "signal"

            # Check stop loss
            if stop_loss_pct:
                sl_price = position["entry_price"] * (1 - stop_loss_pct / 100)
                if row.get("low", close) <= sl_price:
                    should_exit = True
                    close = sl_price  # Salir al precio de SL
                    exit_reason = "stop_loss"

            # Check take profit
            if not should_exit and take_profit_pct:
                tp_price = position["entry_price"] * (1 + take_profit_pct / 100)
                if row.get("high", close) >= tp_price:
                    should_exit = True
                    close = tp_price  # Salir al precio de TP
                    exit_reason = "take_profit"

            # Check exit rules
            if not should_exit and eval_rules(row, prev_row, exit_rules):
                should_exit = True
                close = row.get("close")

            if should_exit:
                pnl = (close - position["entry_price"]) * position["quantity"]
                pnl_pct = (close / position["entry_price"] - 1) * 100
                balance += pnl

                trades.append({
                    "entry_time": position["entry_time"],
                    "exit_time": time,
                    "entry_price": position["entry_price"],
                    "exit_price": close,
                    "quantity": position["quantity"],
                    "pnl": round(pnl, 4),
                    "pnl_pct": round(pnl_pct, 4),
                    "exit_reason": exit_reason,
                })

                position = None

        equity_curve.append({
            "time": time,
            "equity": round(balance + (
                (close - position["entry_price"]) * position["quantity"]
                if position else 0
            ), 4),
        })

    # ── Métricas ──
    winning = [t for t in trades if t["pnl"] > 0]
    losing = [t for t in trades if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in trades)

    metrics = {
        "total_trades": len(trades),
        "winning_trades": len(winning),
        "losing_trades": len(losing),
        "win_rate": round(len(winning) / len(trades) * 100, 2) if trades else 0,
        "total_pnl": round(total_pnl, 4),
        "return_pct": round(total_pnl / position_size * 100, 4) if position_size else 0,
        "avg_pnl": round(total_pnl / len(trades), 4) if trades else 0,
        "best_trade": round(max(t["pnl"] for t in trades), 4) if trades else 0,
        "worst_trade": round(min(t["pnl"] for t in trades), 4) if trades else 0,
        "avg_win": round(sum(t["pnl"] for t in winning) / len(winning), 4) if winning else 0,
        "avg_loss": round(sum(t["pnl"] for t in losing) / len(losing), 4) if losing else 0,
        "max_drawdown": round(calculate_max_drawdown(equity_curve), 4),
        "profit_factor": round(
            sum(t["pnl"] for t in winning) / abs(sum(t["pnl"] for t in losing)), 4
        ) if losing and sum(t["pnl"] for t in losing) != 0 else 999,
    }

    return {
        "trades": trades,
        "metrics": metrics,
        "equity_curve": equity_curve,
    }


def calculate_max_drawdown(equity_curve):
    """Calcula el máximo drawdown en USD."""
    if not equity_curve:
        return 0
    peak = equity_curve[0]["equity"]
    max_dd = 0
    for point in equity_curve:
        eq = point["equity"]
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd
    return max_dd
