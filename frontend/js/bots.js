// ── Bots Tab ──

async function renderBots(content) {
    const data = await api('/bots');
    if (!data || data.bots.length === 0) {
        content.innerHTML = `<div class="card"><div class="empty">
            <div class="empty-icon">⚡</div>
            <div class="empty-text">No hay bots activos.<br>Cuando migres tu bot al sistema, aparecerá aquí.</div>
        </div></div>`;
        return;
    }

    let html = '';
    for (const bot of data.bots) {
        const stats = await api(`/bots/${bot.name}/stats`);
        const orders = await api(`/bots/${bot.name}/orders`);
        html += buildBotCard(bot, stats?.stats, orders?.orders || []);
    }
    content.innerHTML = html;
    if (data.bots.length > 0) initBotChart(data.bots[0]);
}

function buildBotCard(bot, s, orders) {
    s = s || {};
    const pnl = parseFloat(s.total_pnl || 0);
    const ret = parseFloat(s.return_pct || 0);
    const wr = parseFloat(s.win_rate || 0);
    const wallet = parseFloat(s.wallet || 0);
    const best = parseFloat(s.best_trade || 0);
    const worst = parseFloat(s.worst_trade || 0);
    const sells = s.total_sells || 0;
    const date = bot.started_at ? new Date(bot.started_at).toLocaleDateString('es-ES') : '-';
    const active = bot.active;

    return `<div class="card" data-bot="${bot.name}" data-symbol="${bot.symbol}">
        <div class="bot-header">
            <div class="bot-info">
                <div class="bot-icon ${active ? '' : 'inactive'}">${active ? '▶' : '⏸'}</div>
                <div>
                    <div class="bot-name">${bot.name}</div>
                    <div class="bot-strategy">${bot.strategy} · ${bot.symbol} · desde ${date}</div>
                </div>
            </div>
            <div class="bot-badge ${active ? 'active' : 'inactive'}">${active ? 'Activo' : 'Pausado'}</div>
        </div>
        <div class="stats-row">
            <div class="stat-item"><div class="stat-label">PnL Total</div><div class="stat-value ${pnl >= 0 ? 'pos' : 'neg'}">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} $</div></div>
            <div class="stat-item"><div class="stat-label">Rentabilidad</div><div class="stat-value ${ret >= 0 ? 'pos' : 'neg'}">${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%</div></div>
            <div class="stat-item"><div class="stat-label">Win Rate</div><div class="stat-value neu">${wr.toFixed(1)}%</div><div class="stat-sub">${sells} trades</div></div>
            <div class="stat-item"><div class="stat-label">Cartera</div><div class="stat-value neu">${wallet.toFixed(2)} $</div></div>
            <div class="stat-item"><div class="stat-label">Mejor trade</div><div class="stat-value pos">${best > 0 ? '+' : ''}${best.toFixed(2)} $</div></div>
            <div class="stat-item"><div class="stat-label">Peor trade</div><div class="stat-value neg">${worst.toFixed(2)} $</div></div>
        </div>
        <div class="chart-controls">
            ${tfButtons('1h', 'changeBotTf')}
            <div class="chart-divider"></div>
            <button class="ind-btn" onclick="toggleIndicator('ema',this)">EMA</button>
            <button class="ind-btn" onclick="toggleIndicator('sar',this)">SAR</button>
        </div>
        <div id="chart-${bot.name}" style="width:100%;height:500px;"></div>
        ${buildOrdersTable(orders)}
    </div>`;
}

function buildOrdersTable(orders) {
    const header = `<div style="border-top:1px solid var(--border)"><div class="orders-header">
        <div class="orders-title">Historial de órdenes</div>
        <div class="orders-count">${orders.length} órdenes</div></div>`;

    if (!orders.length) return header + `<div style="padding:30px;text-align:center;color:var(--text-muted);font-size:13px">Sin órdenes registradas</div></div>`;

    const rows = orders.map(o => {
        const d = new Date(o.created_at).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
        const pnl = o.side === 'sell' && o.pnl != null ? `<span class="${o.pnl >= 0 ? 'pnl-pos' : 'pnl-neg'}">${o.pnl >= 0 ? '+' : ''}${parseFloat(o.pnl).toFixed(2)}</span>` : '-';
        return `<tr><td>${d}</td><td><span class="side-badge ${o.side}">${o.side.toUpperCase()}</span></td><td>${parseFloat(o.price).toFixed(2)}</td><td>${parseFloat(o.quantity).toFixed(4)}</td><td>${parseFloat(o.cost).toFixed(2)}</td><td>${pnl}</td><td style="color:var(--text-muted)">${o.status}</td></tr>`;
    }).join('');

    return header + `<div style="overflow-x:auto"><table><thead><tr>
        <th>Fecha</th><th>Lado</th><th>Precio</th><th>Cantidad</th><th>Coste</th><th>PnL</th><th>Estado</th>
    </tr></thead><tbody>${rows}</tbody></table></div></div>`;
}

async function initBotChart(bot) {
    makeChart(`chart-${bot.name}`);
    const od = await api(`/bots/${bot.name}/orders`);
    const markers = (od?.orders || []).filter(o => o.price && o.created_at).map(o => ({
        time: toTime(o.created_at),
        position: o.side === 'buy' ? 'belowBar' : 'aboveBar',
        color: o.side === 'buy' ? '#10b981' : '#ef4444',
        shape: o.side === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${o.side.toUpperCase()} ${parseFloat(o.price).toFixed(2)}`,
    }));
    await loadChartData(bot.symbol, '1h', markers);
}

async function changeBotTf(tf, btn) {
    btn.closest('.chart-controls').querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const card = btn.closest('.card');
    const botName = card.dataset.bot;
    const symbol = card.dataset.symbol;
    makeChart(`chart-${botName}`);
    const od = await api(`/bots/${botName}/orders`);
    const markers = (od?.orders || []).filter(o => o.price && o.created_at).map(o => ({
        time: toTime(o.created_at),
        position: o.side === 'buy' ? 'belowBar' : 'aboveBar',
        color: o.side === 'buy' ? '#10b981' : '#ef4444',
        shape: o.side === 'buy' ? 'arrowUp' : 'arrowDown',
        text: `${o.side.toUpperCase()} ${parseFloat(o.price).toFixed(2)}`,
    }));
    await loadChartData(symbol, tf, markers);
}
