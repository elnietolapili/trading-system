// ── Strategies Tab ──

let operators = [];
let indicators = [];
let allCollections = [];
let allStrategies = [];
let selectedCollectionId = null;

async function renderStrategies(content) {
    const ops = await api('/strategies/operators');
    if (ops) { operators = ops.operators; indicators = ops.indicators; }

    const data = await api('/collections');
    if (data) { allCollections = data.collections; allStrategies = data.strategies; }

    content.innerHTML = `
        <div style="display:flex;gap:8px;margin-bottom:16px;">
            <button class="btn btn-primary btn-sm" onclick="openCreateStrategy()">+ Nueva estrategia</button>
            <button class="btn btn-ghost btn-sm" onclick="openCreateCollection()">+ Nueva colección</button>
        </div>
        <div style="display:flex;gap:20px;">
            <div id="sidebar" style="width:240px;flex-shrink:0;">
                <div class="card" style="margin-bottom:0;">
                    <div class="card-header"><div class="card-title">Colecciones</div></div>
                    <div id="col-tree" style="padding:8px 0;">${buildCollectionTree(null, 0)}</div>
                    <div class="strat-item" onclick="selectCollection(null)" style="${selectedCollectionId === null ? 'background:var(--bg-hover)' : ''}">
                        <div><div class="strat-meta">📋 Sin colección</div></div>
                    </div>
                </div>
            </div>
            <div id="strat-main" style="flex:1;min-width:0;">
                <div class="card">
                    <div class="card-header">
                        <div class="card-title" id="strat-list-title">${getCollectionTitle()}</div>
                        <div class="orders-count">${getFilteredStrategies().length} estrategias</div>
                    </div>
                    <div id="strat-list">${buildStratList()}</div>
                </div>
                <div id="strat-detail"></div>
            </div>
        </div>
    `;
}

// ── Collection tree ──

function buildCollectionTree(parentId, depth) {
    const children = allCollections.filter(c => c.parent_id === parentId);
    if (!children.length) return '';

    return children.map(c => {
        const sub = buildCollectionTree(c.id, depth + 1);
        const stratCount = allStrategies.filter(s => s.collection_id === c.id).length;
        const isSelected = selectedCollectionId === c.id;
        const pad = depth * 16;

        return `<div>
            <div class="strat-item" onclick="selectCollection(${c.id})" style="padding-left:${20 + pad}px;${isSelected ? 'background:var(--bg-hover)' : ''}">
                <div>
                    <div class="strat-name" style="font-size:13px;">${sub ? '▼' : '▸'} ${c.name}</div>
                    <div class="strat-meta">${stratCount} estrategia${stratCount !== 1 ? 's' : ''}</div>
                </div>
                <div class="strat-actions">
                    <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();openEditCollection(${c.id},'${c.name}')">✎</button>
                    <button class="btn btn-red btn-sm" onclick="event.stopPropagation();deleteCollection(${c.id})">✕</button>
                </div>
            </div>
            ${sub}
        </div>`;
    }).join('');
}

function selectCollection(id) {
    selectedCollectionId = id;
    renderTab('strategies');
}

function getCollectionTitle() {
    if (selectedCollectionId === null) return 'Sin colección';
    const col = allCollections.find(c => c.id === selectedCollectionId);
    return col ? col.name : 'Todas';
}

function getFilteredStrategies() {
    return allStrategies.filter(s => s.collection_id === selectedCollectionId);
}

// ── Strategy list ──

function buildStratList() {
    const strats = getFilteredStrategies();
    if (!strats.length) return `<div class="empty"><div class="empty-text">No hay estrategias en esta colección.</div></div>`;
    return strats.map(s => buildStratItem(s)).join('');
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
            <button class="btn btn-green btn-sm" onclick="event.stopPropagation();runBacktest(${s.id})">Backtest</button>
            <button class="btn btn-ghost btn-sm" onclick="event.stopPropagation();openEditStrategy(${s.id})">Editar</button>
            <button class="btn btn-red btn-sm" onclick="event.stopPropagation();deleteStrategy(${s.id})">✕</button>
        </div>
    </div>`;
}

// ── Collection CRUD ──

function openCreateCollection() {
    const parentOptions = allCollections.map(c => `<option value="${c.id}">${c.name}</option>`).join('');
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `<div class="modal">
        <div class="modal-title">Nueva colección</div>
        <div class="form-group">
            <label class="form-label">Nombre</label>
            <input type="text" class="form-input" id="col-name" placeholder="Scalping, Swing, Pruebas...">
        </div>
        <div class="form-group">
            <label class="form-label">Dentro de (opcional)</label>
            <select class="form-select" id="col-parent">
                <option value="">-- Raíz --</option>
                ${parentOptions}
            </select>
        </div>
        <div class="btn-group">
            <button class="btn btn-primary" onclick="saveNewCollection()">Crear</button>
            <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
        </div>
    </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

async function saveNewCollection() {
    const name = document.getElementById('col-name').value.trim();
    if (!name) { alert('Pon un nombre'); return; }
    const parentVal = document.getElementById('col-parent').value;
    await apiPost('/collections', { name, parent_id: parentVal ? parseInt(parentVal) : null });
    document.querySelector('.modal-overlay')?.remove();
    renderTab('strategies');
}

function openEditCollection(id, name) {
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.innerHTML = `<div class="modal">
        <div class="modal-title">Editar colección</div>
        <div class="form-group">
            <label class="form-label">Nombre</label>
            <input type="text" class="form-input" id="edit-col-name" value="${name}">
        </div>
        <div class="btn-group">
            <button class="btn btn-primary" onclick="saveEditCollection(${id})">Guardar</button>
            <button class="btn btn-ghost" onclick="this.closest('.modal-overlay').remove()">Cancelar</button>
        </div>
    </div>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

async function saveEditCollection(id) {
    const name = document.getElementById('edit-col-name').value.trim();
    if (!name) return;
    await apiPut(`/collections/${id}`, { name });
    document.querySelector('.modal-overlay')?.remove();
    renderTab('strategies');
}

async function deleteCollection(id) {
    if (!confirm('¿Eliminar esta colección? Las estrategias dentro quedarán sin colección.')) return;
    await apiDelete(`/collections/${id}`);
    if (selectedCollectionId === id) selectedCollectionId = null;
    renderTab('strategies');
}
