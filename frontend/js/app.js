// ── Config ──
const API_URL = '/api';

// ── State ──
let chart = null;
let candleSeries = null;
let emaSeries = {};
let sarSeries = null;
let equityChart = null;
let equitySeries = null;

// ── API ──
async function api(path, options = {}) {
    try {
        const res = await fetch(`${API_URL}${path}`, options);
        return await res.json();
    } catch (err) {
        document.getElementById('system-status').textContent = 'Sin conexión';
        return null;
    }
}

async function apiPost(path, body) {
    return api(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
}

async function apiPut(path, body) {
    return api(path, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
}

async function apiDelete(path) {
    return api(path, { method: 'DELETE' });
}

// ── Tab routing ──
function renderTab(tab) {
    const content = document.getElementById('content');
    content.innerHTML = '<div class="loading"><div class="spinner"></div> Cargando...</div>';

    if (tab === 'bots') renderBots(content);
    else if (tab === 'analysis') renderAnalysis(content);
    else if (tab === 'strategies') renderStrategies(content);
}

// ── Chart helpers ──
function toTime(iso) {
    return Math.floor(new Date(iso).getTime() / 1000);
}

function makeChart(containerId, height = 500) {
    const el = document.getElementById(containerId);
    if (!el) return null;
    if (chart) { chart.remove(); chart = null; }

    chart = LightweightCharts.createChart(el, {
        width: el.clientWidth,
        height: height,
        layout: { background: { color: '#151d2e' }, textColor: '#8892a5', fontFamily: "'JetBrains Mono', monospace" },
        grid: { vertLines: { color: '#1e2a3f' }, horzLines: { color: '#1e2a3f' } },
        crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
        timeScale: { timeVisible: true, secondsVisible: false },
        rightPriceScale: { borderColor: '#1e2a3f' },
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#10b981', downColor: '#ef4444',
        borderDownColor: '#ef4444', borderUpColor: '#10b981',
        wickDownColor: '#ef4444', wickUpColor: '#10b981',
    });

    emaSeries = {
        ema_9: chart.addLineSeries({ color: '#fbbf24', lineWidth: 1, title: 'EMA 9', visible: false }),
        ema_20: chart.addLineSeries({ color: '#f97316', lineWidth: 1, title: 'EMA 20', visible: false }),
        ema_50: chart.addLineSeries({ color: '#3b82f6', lineWidth: 1, title: 'EMA 50', visible: false }),
        ema_200: chart.addLineSeries({ color: '#ec4899', lineWidth: 1, title: 'EMA 200', visible: false }),
    };

    sarSeries = chart.addLineSeries({
        color: '#a78bfa', lineWidth: 0,
        pointMarkersVisible: true, pointMarkersRadius: 2,
        title: 'SAR', visible: false,
    });

    return chart;
}

async function loadChartData(symbol, tf, markers = []) {
    const data = await api(`/candles?symbol=${symbol}&timeframe=${tf}&limit=1000000`);
    if (!data || !data.candles.length) return;

    candleSeries.setData(data.candles.map(c => ({
        time: toTime(c.time), open: c.open, high: c.high, low: c.low, close: c.close,
    })));

    ['ema_9', 'ema_20', 'ema_50', 'ema_200'].forEach(k => {
        emaSeries[k].setData(data.candles.filter(c => c[k] != null).map(c => ({ time: toTime(c.time), value: c[k] })));
    });

    sarSeries.setData(data.candles.filter(c => c.sar_015 != null).map(c => ({ time: toTime(c.time), value: c.sar_015 })));

    if (markers.length) {
        candleSeries.setMarkers(markers.sort((a, b) => a.time - b.time));
    }

    chart.timeScale().fitContent();
}

function toggleIndicator(type, btn) {
    btn.classList.toggle('active');
    const on = btn.classList.contains('active');
    if (type === 'ema') Object.values(emaSeries).forEach(s => s.applyOptions({ visible: on }));
    else sarSeries.applyOptions({ visible: on });
}

function makeEquityChart(containerId, equityCurve) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (equityChart) { equityChart.remove(); equityChart = null; }

    equityChart = LightweightCharts.createChart(el, {
        width: el.clientWidth,
        height: 200,
        layout: { background: { color: '#151d2e' }, textColor: '#8892a5', fontFamily: "'JetBrains Mono', monospace" },
        grid: { vertLines: { color: '#1e2a3f' }, horzLines: { color: '#1e2a3f' } },
        rightPriceScale: { borderColor: '#1e2a3f' },
        timeScale: { timeVisible: true, secondsVisible: false },
    });

    equitySeries = equityChart.addAreaSeries({
        topColor: 'rgba(16, 185, 129, 0.3)',
        bottomColor: 'rgba(16, 185, 129, 0.02)',
        lineColor: '#10b981',
        lineWidth: 2,
    });

    equitySeries.setData(equityCurve.map(p => ({ time: toTime(p.time), value: p.equity })));
    equityChart.timeScale().fitContent();
}

// ── Timeframe buttons builder ──
function tfButtons(activeId, onClickFn) {
    return ['1h', '2h', '4h', '8h', '12h', '1D', '1W'].map(tf =>
        `<button class="tf-btn ${tf === '1h' ? 'active' : ''}" onclick="${onClickFn}('${tf}', this)">${tf}</button>`
    ).join('');
}

// ── Resize ──
window.addEventListener('resize', () => {
    if (chart) chart.applyOptions({ width: chart.chartElement().parentElement.clientWidth });
    if (equityChart) equityChart.applyOptions({ width: equityChart.chartElement().parentElement.clientWidth });
});
