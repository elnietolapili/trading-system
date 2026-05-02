// ── Strategy Detail & Backtest ──

function describeRule(rule) {
    const ind = indicators.find(i => i.id === rule.indicator);
    const op = operators.find(o => o.id === rule.operator);
    const valInd = indicators.find(i => i.id === rule.value);
    const indLabel = ind ? ind.label : rule.indicator;
    const opLabel = op ? op.label : rule.operator;
    const valLabel = valInd ? valInd.label : rule.value;
    return `${indLabel} ${opLabel} ${valLabel}`;
}

function buildStrategyExplanation(s) {
    const entryRules = (s.entry_rules || []).map(r => describeRule(r));
    const exitRules = (s.exit_rules || []).map(r => describeRule(r));

    return `<div style="padding:20px;">
        <div style="font-size:15px;font-weight:600;margin-bottom:16px;">${s.name}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;">
            <div>
                <div class="section-label" style="margin-top:0;">Configuración</div>
                <div style="font-size:13px;line-height:2;color:var(--text-secondary);">
                    <div><span style="color:var(--text-muted)">Símbolo:</span> <span style="color:var(--text-primary)">${s.symbol}</span></div>
                    <div><span style="color:var(--text-muted)">Timeframe:</span> <span style="color:var(--text-primary)">${s.timeframe}</span></div>
                    <div><span style="color:var(--text-muted)">Tamaño posición:</span> <span style="color:var(--text-primary)">${s.position_size} $</span></div>
                    <div><span style="color:var(--text-muted)">Stop Loss:</span> <span style="color:var(--text-primary)">${s.stop_loss_pct ? s.stop_loss_pct + '%' : 'Sin SL'}</span></div>
                    <div><span style="color:var(--text-muted)">Take Profit:</span> <span style="color:var(--text-primary)">${s.take_profit_pct ? s.take_profit_pct + '%' : 'Sin TP'}</span></div>
                </div>
            </div>
            <div>
                <div class="section-label" style="margin-top:0;color:var(--green);">Entrada (todas deben cumplirse)</div>
                <div style="font-size:13px;line-height:2;">
                    ${entryRules.map(r => `<div style="color:var(--green);">▸ ${r}</div>`).join('')}
                </div>
                <div class="section-label" style="color:var(--red);">Salida (todas deben cumplirse)</div>
                <div style="font-size:13px;line-height:2;">
                    ${exitRules.map(r => `<div style="color:var(--red);">▸ ${r}</div>`).join('')}
                </div>
                ${s.stop_loss_pct ? `<div style="font-size:12px;color:var(--text-muted);margin-top:4px;">+ Stop Loss automático al ${s.stop_loss_pct}% desde entrada</div>` : ''}
                ${s.take_profit_pct ? `<div style="font-size:12px;color:var(--text-muted);">+ Take Profit automático al ${s.take_profit_pct}% desde entrada</div>` : ''}
            </div>
        </div>
    </div>`;
}

async function viewStrategy(id) {
    const s = allStrategies.find(x => x.id === id);
    if (!s) return;

    const detail = document.getElementById('strat-detail');

    if (s.last_backtest) {
        const result = typeof s.last_backtest === 'string' ? JSON.parse(s.last_backtest) : s.last_backtest;
        detail.innerHTML = `<div class="card">
            ${buildStrategyExplanation(s)}
            <div style="border-top:1px solid var(--border);"></div>
            ${buildBacktestStats(s, result)}
            <div id="bt-chart" style="width:100%;height:450px;"></div>
            <div class="equity-container">
                <div class="equity-title">Curva de equity</div>
                <div id="bt-equity" style="width:100%;height:200px;"></div>
            </div>
            ${buildTradesTable(result.trades)}
        </div>`;

        const markers = buildTradeMarkers(result.trades);
        makeChart('bt-chart', 450);
        loadChartData(s.symbol, s.timeframe, markers);
        makeEquityChart('bt-equity', result.equity_curve);
    } else {
        detail.innerHTML = `<div class="card">
            ${buildStrategyExplanation(s)}
            <div style="padding:30px;text-align:center;border-top:1px solid var(--border);">
                <div style="color:var(--text-muted);font-size:13px;margin-bottom:12px;">Sin backtest todavía</div>
                <button class="btn btn-green" onclick="runBacktest(${id})">Ejecutar backtest</button>
            </div>
        </div>`;
    }
}

// ── Backtest ──

async function runBacktest(id) {
    const detail = document.getElementById('strat-detail');
    detail.innerHTML = '<div class="loading"><div class="spinner"></div> Ejecutando backtest...</div>';

    const res = await apiPost(`/strategies/${id}/backtest`);
    if (!res || res.error) {
        detail.innerHTML = `<div class="card"><div class="empty"><div class="empty-text">${res?.error || 'Error al ejecutar backtest'}</div></div></div>`;
        return;
    }

    // Refresh strategies data
    const data = await api('/collections');
    if (data) { allCollections = data.collections; allStrategies = data.strategies; }

    viewStrategy(id);
}

function buildBacktestStats(s, result) {
    const m = result.metrics;
    return `<div class="stats-row">
        <div class="stat-item"><div class="stat-label">PnL Total</div><div class="stat-value ${m.total_pnl >= 0 ? 'pos' : 'neg'}">${m.total_pnl >= 0 ? '+' : ''}${m.total_pnl.toFixed(2)} $</div></div>
        <div class="stat-item"><div class="stat-label">Rentabilidad</div><div class="stat-value ${m.return_pct >= 0 ? 'pos' : 'neg'}">${m.return_pct >= 0 ? '+' : ''}${m.return_pct.toFixed(2)}%</div></div>
        <div class="stat-item"><div class="stat-label">Win Rate</div><div class="stat-value neu">${m.win_rate}%</div><div class="stat-sub">${m.total_trades} trades</div></div>
        <div class="stat-item"><div class="stat-label">Profit Factor</div><div class="stat-value neu">${m.profit_factor.toFixed(2)}</div></div>
        <div class="stat-item"><div class="stat-label">Mejor trade</div><div class="stat-value pos">+${m.best_trade.toFixed(2)} $</div></div>
        <div class="stat-item"><div class="stat-label">Peor trade</div><div class="stat-value neg">${m.worst_trade.toFixed(2)} $</div></div>
        <div class="stat-item"><div class="stat-label">Max Drawdown</div><div class="stat-value neg">-${m.max_drawdown.toFixed(2)} $</div></div>
        <div class="stat-item"><div class="stat-label">Media ganancia</div><div class="stat-value pos">+${m.avg_win.toFixed(2)} $</div></div>
    </div>
    <div class="chart-controls"><span style="font-size:12px;color:var(--text-secondary)">Gráfica con señales</span></div>`;
}

function buildTradeMarkers(trades) {
    return trades.flatMap(t => [
        { time: toTime(t.entry_time), position: 'belowBar', color: '#10b981', shape: 'arrowUp', text: `BUY ${t.entry_price.toFixed(2)}` },
        { time: toTime(t.exit_time), position: 'aboveBar', color: '#ef4444', shape: 'arrowDown', text: `SELL ${t.exit_price.toFixed(2)}` },
    ]);
}

function buildTradesTable(trades) {
    if (!trades.length) return '';

    const rows = trades.map(t => {
        const entry = new Date(t.entry_time).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
        const exit = new Date(t.exit_time).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
        return `<tr>
            <td>${entry}</td><td>${t.entry_price.toFixed(2)}</td>
            <td>${exit}</td><td>${t.exit_price.toFixed(2)}</td>
            <td class="${t.pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}</td>
            <td class="${t.pnl_pct >= 0 ? 'pnl-pos' : 'pnl-neg'}">${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(2)}%</td>
            <td style="color:var(--text-muted)">${t.exit_reason}</td>
        </tr>`;
    }).join('');

    return `<div style="border-top:1px solid var(--border)">
        <div class="orders-header">
            <div class="orders-title">Trades simulados</div>
            <div class="orders-count">${trades.length} trades</div>
        </div>
        <div style="overflow-x:auto"><table><thead><tr>
            <th>Entrada</th><th>Precio entrada</th><th>Salida</th><th>Precio salida</th><th>PnL</th><th>PnL %</th><th>Razón</th>
        </tr></thead><tbody>${rows}</tbody></table></div>
    </div>`;
}
