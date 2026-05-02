// ── Strategy Form (Create / Edit) ──

function ruleRow(rule = {}, prefix = 'entry') {
    const indOpts = indicators.map(i => `<option value="${i.id}" ${rule.indicator === i.id ? 'selected' : ''}>${i.label}</option>`).join('');
    const opOpts = operators.map(o => `<option value="${o.id}" ${rule.operator === o.id ? 'selected' : ''}>${o.label}</option>`).join('');
    const val = rule.value || '';
    const isInd = indicators.some(i => i.id === val);
    const valOpts = indicators.map(i => `<option value="${i.id}" ${val === i.id ? 'selected' : ''}>${i.label}</option>`).join('');

    return `<div class="rule-row" data-prefix="${prefix}">
        <select class="rule-indicator">${indOpts}</select>
        <select class="rule-operator">${opOpts}</select>
        <select class="rule-value">
            <option value="">-- valor --</option>
            ${valOpts}
            <option value="__custom" ${!isInd && val !== '' ? 'selected' : ''}>Número...</option>
        </select>
        <input type="number" class="rule-custom-value" placeholder="0" value="${!isInd ? val : ''}" style="${isInd || val === '' ? 'display:none' : ''}">
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
    sel.addEventListener('change', () => { input.style.display = sel.value === '__custom' ? '' : 'none'; });
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

function collectionSelect(selectedId = null) {
    const opts = allCollections.map(c => `<option value="${c.id}" ${selectedId === c.id ? 'selected' : ''}>${c.name}</option>`).join('');
    return `<select class="form-select" id="strat-collection">
        <option value="">-- Seleccionar colección --</option>
        ${opts}
    </select>`;
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
                <label class="form-label">Colección *</label>
                ${collectionSelect(selectedCollectionId)}
            </div>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">Símbolo</label>
                <select class="form-select" id="strat-symbol">
                    <option value="ETHUSDT">ETH/USDT</option>
                    <option value="BTCUSDT">BTC/USDT</option>
                    <option value="BNBUSDT">BNB/USDT</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label">Timeframe</label>
                <select class="form-select" id="strat-tf">
                    <option value="1h">1H</option><option value="2h">2H</option><option value="4h">4H</option>
                    <option value="8h">8H</option><option value="12h">12H</option><option value="1D">1D</option><option value="1W">1W</option>
                </select>
            </div>
        </div>
        <div class="form-row-3">
            <div class="form-group">
                <label class="form-label">Stop Loss %</label>
                <input type="number" class="form-input" id="strat-sl" placeholder="3" step="0.1">
            </div>
            <div class="form-group">
                <label class="form-label">Take Profit %</label>
                <input type="number" class="form-input" id="strat-tp" placeholder="6" step="0.1">
            </div>
            <div class="form-group">
                <label class="form-label">Tamaño posición ($)</label>
                <input type="number" class="form-input" id="strat-size" value="1000" step="100">
            </div>
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
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

async function saveNewStrategy() {
    const name = document.getElementById('strat-name').value.trim();
    if (!name) { alert('Pon un nombre'); return; }
    const colVal = document.getElementById('strat-collection').value;
    if (!colVal) { alert('Selecciona una colección'); return; }

    const body = {
        name,
        symbol: document.getElementById('strat-symbol').value,
        timeframe: document.getElementById('strat-tf').value,
        entry_rules: collectRules('entry'),
        exit_rules: collectRules('exit'),
        stop_loss_pct: parseFloat(document.getElementById('strat-sl').value) || null,
        take_profit_pct: parseFloat(document.getElementById('strat-tp').value) || null,
        position_size: parseFloat(document.getElementById('strat-size').value) || 1000,
        collection_id: parseInt(colVal),
    };

    const res = await apiPost('/strategies', body);
    if (res?.error) { alert(res.error); return; }
    document.querySelector('.modal-overlay')?.remove();
    selectedCollectionId = parseInt(colVal);
    renderTab('strategies');
}

async function openEditStrategy(id) {
    const s = allStrategies.find(x => x.id === id);
    if (!s) return;

    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `<div class="modal">
        <div class="modal-title">Editar: ${s.name}</div>
        <div class="form-group">
            <label class="form-label">Colección</label>
            ${collectionSelect(s.collection_id)}
        </div>
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
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

async function saveEditStrategy(id) {
    const colVal = document.getElementById('strat-collection').value;
    const body = {
        entry_rules: collectRules('entry'),
        exit_rules: collectRules('exit'),
        stop_loss_pct: parseFloat(document.getElementById('edit-sl').value) || null,
        take_profit_pct: parseFloat(document.getElementById('edit-tp').value) || null,
        position_size: parseFloat(document.getElementById('edit-size').value) || 1000,
    };
    if (colVal) body.collection_id = parseInt(colVal);

    await apiPut(`/strategies/${id}`, body);
    document.querySelector('.modal-overlay')?.remove();
    renderTab('strategies');
}

async function deleteStrategy(id) {
    if (!confirm('¿Eliminar esta estrategia?')) return;
    await apiDelete(`/strategies/${id}`);
    renderTab('strategies');
}
