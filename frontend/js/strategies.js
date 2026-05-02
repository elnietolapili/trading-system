// ── Strategies Tab ──

let operators = [];
let indicators = [];

async function renderStrategies(content) {
    // Load operators/indicators
    const ops = await api('/strategies/operators');
    if (ops) {
        operators = ops.operators;
        indicators = ops.indicators;
    }

    const data = await api('/strategies');
    const strategies = data?.strategies || [];

    content.innerHTML = `
        <div class="card">
            <div class="card-header">
                <div class="card-title">Estrategias guardadas</div>
                <button class="btn btn-primary btn-sm" onclick="openCreateStrategy()">+ Nueva estrategia</button>
            </div>
            <div id="strat-list">
                ${strategies.length === 0 ? `<div class="empty"><div class="empty-icon">📊</div><div class="empty-text">No hay estrategias. Crea la primera.</div></div>` :
                strategies.map(s => buildStratItem(s)).join('')}
            </div>
        </div>
        <div id="strat-detail"></div>
    `;
}

function buildStratItem(s) {
    const entryCount = s.entry_rules ? s.entry_rules.length : 0;
    const exitCount = s.exit_rules ? s.exit_rules.length : 0;
    const hasBacktest = s.backtest_at;

    return `<div class="strat-item" onclick="viewStrategy(${s.id})">
        <div>
            <div class="strat-name">${s.name}</div>
            <div class="strat-meta">${s.symbol} · ${s.timeframe} · ${entryCount} entrada · ${exitCount} salida ${hasBacktest ? '· ✓ backtested' : ''}</div>
        </div>
        <div class="strat-actions">
            <button class="btn btn-green btn-sm" onclick="event.stopPropagation(); runBacktest(${s.id})">Backtest</button>
            <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation(); openEditStrategy(${s.id})">Editar</button>
            <button class="btn btn-red btn-sm" onclick="event.stopPropagation(); deleteStrategy(${s.id})">✕</button>
        </div>
    </div>`;
}

// ── Create / Edit Modal ──

function ruleRow(rule = {}, prefix = 'entry') {
    const indOptions = indicators.map(i => `<option value="${i.id}" ${rule.indicator === i.id ? 'selected' : ''}>${i.label}</option>`).join('');
    const opOptions = operators.map(o => `<option value="${o.id}" ${rule.operator === o.id ? 'selected' : ''}>${o.label}</option>`).join('');
    const val = rule.value || '';
    const isIndicatorValue = indicators.some(i => i.id === val);

    // Value can be indicator or number
    const valOptions = indicators.map(i => `<option value="${i.id}" ${val === i.id ? 'selected' : ''}>${i.label}</option>`).join('');

    return `<div class="rule-row" data-prefix="${prefix}">
        <select class="rule-indicator">${indOptions}</select>
        <select class="rule-operator">${opOptions}</select>
        <select class="rule-value">
            <option value="">-- valor --</option>
            ${valOptions}
            <option value="__custom" ${!isIndicatorValue && val !== '' ? 'selected' : ''}>Número...</option>
        </select>
        <input type="number" class="rule-custom-value" placeholder="0" value="${!isIndicatorValue ? val : ''}" style="${isIndicatorValue || val === '' ? 'display:none' : ''}">
        <button class="rule-remove" onclick="this.closest('.rule-row').remove()">✕</button>
    </div>`;
}

function rulesSection(label, prefix, rules = []) {
    const rows = rules.length > 0 ? rules.map(r => ruleRow(r, prefix)).join('') : ruleRow({}, prefix);
    return `
        <div class="section-label">${label}</div>
        <div id="${prefix}-rules">${rows}</div>
        <button class="add-rule" onclick="addRule('${prefix}')">+ Añadir condición</button>
    `;
}

function addRule(prefix) {
    const container = document.getElementById(`${prefix}-rules`);
    container.insertAdjacentHTML('beforeend', ruleRow({}, prefix));
    attachValueToggle(container.lastElementChild);
}

function attachValueToggle(row) {
    const sel = row.querySelector('.rule-value');
    const input = row.querySelector('.rule-custom-value');
    sel.addEventListener('change', () => {
        input.style.display = sel.value === '__custom' ? '' : 'none';
    });
}

function attachAllValueToggles() {
    document.querySelectorAll('.rule-row').forEach(row => attachValueToggle(row));
}

function collectRules(prefix) {
    const rules = [];
    document.querySelectorAll(`#${prefix}-rules .rule-row`).forEach(row => {
        const indicator = row.querySelector('.rule-indicator').value;
        const operator = row.querySelector('.rule-operator').value;
        const valueSel = row.querySelector('.rule-value').value;
        const customVal = row.querySelector('.rule-custom-value').value;

        let value = valueSel === '__custom' ? parseFloat(customVal) : valueSel;
        if (indicator && operator && (value !== '' && value !== null)) {
            rules.push({ indicator, operator, value });
        }
    });
    return rules;
}

function openCreateStrategy() {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `<div class="modal">
        <div class="modal-title">Nueva estrategia</div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Nombre</label>
                <input type="text" class="form-input" id="strat-name" placeholder="Mi estrategia">
            </div>
            <div class="form-group">
                <label class="form-label">Símbolo</label>
                <select class="form-select" id="strat-symbol">
                    <option value="ETHUSDT">ETH/USDT</option>
                    <option value="BTCUSDT">BTC/USDT</option>
                    <option value="BNBUSDT">BNB/USDT</option>
                </select>
            </div>
        </div>
        <div class="form-row-3">
            <div class="form-group">
                <label class="form-label">Timeframe</label>
                <select class="form-select" id="strat-tf">
                    <option value="1h">1H</option>
                    <option value="2h">2H</option>
                    <option value="4h">4H</option>
                    <option value="8h">8H</option>
                    <option value="12h">12H</option>
                    <option value="1D">1D</option>
                    <option value="1W">1W</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Stop Loss %</label>
                <input type="number" class="form-input" id="strat-sl" placeholder="3" step="0.1">
            </div>
            <div class="form-group">
                <label class="form-label">Take Profit %</label>
                <input type="number" class="form-input" id="strat-tp" placeholder="6" step="0.1">
            </div>
        </div>
        <div class="form-group">
            <label class="form-label">Tamaño posición ($)</label>
            <input type="number" class="form-input" id="strat-size" value="1000" step="100">
        </div>
        ${rulesSection('Reglas de entrada (AND)', 'entry')}
        ${rulesSection('Reglas de salida (AND)', 'exit')}
        <div class="btn-group">
            <button class="btn btn-primary" onclick="saveNewStrategy()">Crear estrategia</button>
            <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
        </div>
    </div>`;
    document.body.appendChild(modal);
    attachAllValueToggles();
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}

async function saveNewStrategy() {
    const name = document.getElementById('strat-name').value.trim();
    if (!name) { alert('Pon un nombre'); return; }

    const body = {
        name,
        symbol: document.getElementById('strat-symbol').value,
        timeframe: document.getElementById('strat-tf').value,
        entry_rules: collectRules('entry'),
        exit_rules: collectRules('exit'),
        stop_loss_pct: parseFloat(document.getElementById('strat-sl').value) || null,
        take_profit_pct: parseFloat(document.getElementById('strat-tp').value) || null,
        position_size: parseFloat(document.getElementById('strat-size').value) || 1000,
    };

    const res = await apiPost('/strategies', body);
    if (res?.error) { alert(res.error); return; }

    document.querySelector('.modal-overlay')?.remove();
    renderTab('strategies');
}

async function openEditStrategy(id) {
    const data = await api('/strategies');
    const s = data?.strategies?.find(x => x.id === id);
    if (!s) return;

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `<div class="modal">
        <div class="modal-title">Editar: ${s.name}</div>
        <div class="form-row-3">
            <div class="form-group">
                <label class="form-label">Stop Loss %</label>
                <input type="number" class="form-input" id="edit-sl" value="${s.stop_loss_pct || ''}" step="0.1">
            </div>
            <div class="form-group">
                <label class="form-label">Take Profit %</label>
                <input type="number" class="form-input" id="edit-tp" value="${s.take_profit_pct || ''}" step="0.1">
            </div>
            <div class="form-group">
                <label class="form-label">Tamaño posición ($)</label>
                <input type="number" class="form-input" id="edit-size" value="${s.position_size || 1000}" step="100">
            </div>
        </div>
        ${rulesSection('Reglas de entrada (AND)', 'entry', s.entry_rules || [])}
        ${rulesSection('Reglas de salida (AND)', 'exit', s.exit_rules || [])}
        <div class="btn-group">
            <button class="btn btn-primary" onclick="saveEditStrategy(${id})">Guardar cambios</button>
            <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
        </div>
    </div>`;
    document.body.appendChild(modal);
    attachAllValueToggles();
    modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
}

async function saveEditStrategy(id) {
    const body = {
        entry_rules: collectRules('entry'),
        exit_rules: collectRules('exit'),
        stop_loss_pct: parseFloat(document.getElementById('edit-sl').value) || null,
        take_profit_pct: parseFloat(document.getElementById('edit-tp').value) || null,
        position_size: parseFloat(document.getElementById('edit-size').value) || 1000,
    };

    await apiPut(`/strategies/${id}`, body);
    document.querySelector('.modal-overlay')?.remove();
    renderTab('strategies');
}

async function deleteStrategy(id) {
    if (!confirm('¿Eliminar esta estrategia?')) return;
    await apiDelete(`/strategies/${id}`);
    renderTab('strategies');
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

    renderBacktestResults(res);
}

function renderBacktestResults(res) {
    const m = res.result.metrics;
    const trades = res.result.trades;
    const equity = res.result.equity_curve;
    const detail = document.getElementById('strat-detail');

    // Build trade markers for chart
    const markers = trades.flatMap(t => [
        { time: toTime(t.entry_time), position: 'belowBar', color: '#10b981', shape: 'arrowUp', text: `BUY ${t.entry_price.toFixed(2)}` },
        { time: toTime(t.exit_time), position: 'aboveBar', color: '#ef4444', shape: 'arrowDown', text: `SELL ${t.exit_price.toFixed(2)}` },
    ]);

    detail.innerHTML = `
        <div class="card">
            <div class="card-header">
                <div class="card-title">Resultado: ${res.strategy_name}</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--text-secondary)">${res.symbol} · ${res.timeframe} · ${res.candles_used} velas</div>
            </div>
            <div class="stats-row">
                <div class="stat-item"><div class="stat-label">PnL Total</div><div class="stat-value ${m.total_pnl >= 0 ? 'pos' : 'neg'}">${m.total_pnl >= 0 ? '+' : ''}${m.total_pnl.toFixed(2)} $</div></div>
                <div class="stat-item"><div class="stat-label">Rentabilidad</div><div class="stat-value ${m.return_pct >= 0 ? 'pos' : 'neg'}">${m.return_pct >= 0 ? '+' : ''}${m.return_pct.toFixed(2)}%</div></div>
                <div class="stat-item"><div class="stat-label">Win Rate</div><div class="stat-value neu">${m.win_rate}%</div><div class="stat-sub">${m.total_trades} trades</div></div>
                <div class="stat-item"><div class="stat-label">Profit Factor</div><div class="stat-value neu">${m.profit_factor.toFixed(2)}</div></div>
                <div class="stat-item"><div class="stat-label">Mejor trade</div><div class="stat-value pos">+${m.best_trade.toFixed(2)} $</div></div>
                <div class="stat-item"><div class="stat-label">Peor trade</div><div class="stat-value neg">${m.worst_trade.toFixed(2)} $</div></div>
                <div class="stat-item"><div class="stat-label">Max Drawdown</div><div class="stat-value neg">-${m.max_drawdown.toFixed(2)} $</div></div>
                <div class="stat-item"><div class="stat-label">Media ganancia</div><div class="stat-value pos">+${m.avg_win.toFixed(2)} $</div></div>
            </div>

            <!-- Chart with trade markers -->
            <div class="chart-controls">
                <span style="font-size:12px;color:var(--text-secondary)">Gráfica con señales</span>
            </div>
            <div id="bt-chart" style="width:100%;height:450px;"></div>

            <!-- Equity curve -->
            <div class="equity-container">
                <div class="equity-title">Curva de equity</div>
                <div id="bt-equity" style="width:100%;height:200px;"></div>
            </div>

            <!-- Trades table -->
            ${buildTradesTable(trades)}
        </div>
    `;

    // Init charts
    makeChart('bt-chart', 450);
    loadChartData(res.symbol, res.timeframe, markers);
    makeEquityChart('bt-equity', equity);
}

function buildTradesTable(trades) {
    if (!trades.length) return '';

    const rows = trades.map(t => {
        const entry = new Date(t.entry_time).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
        const exit = new Date(t.exit_time).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
        return `<tr>
            <td>${entry}</td>
            <td>${t.entry_price.toFixed(2)}</td>
            <td>${exit}</td>
            <td>${t.exit_price.toFixed(2)}</td>
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

// ── View strategy detail ──

async function viewStrategy(id) {
    const data = await api('/strategies');
    const s = data?.strategies?.find(x => x.id === id);
    if (!s) return;

    if (s.last_backtest) {
        // Reconstruct the result format
        const res = {
            strategy_name: s.name,
            symbol: s.symbol,
            timeframe: s.timeframe,
            candles_used: '-',
            result: typeof s.last_backtest === 'string' ? JSON.parse(s.last_backtest) : s.last_backtest,
        };
        renderBacktestResults(res);
    } else {
        document.getElementById('strat-detail').innerHTML = `<div class="card"><div class="empty">
            <div class="empty-text">Esta estrategia no tiene backtest. Pulsa "Backtest" para ejecutarlo.</div>
        </div></div>`;
    }
}
