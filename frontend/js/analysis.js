// ── Analysis Tab ──

function renderAnalysis(content) {
    content.innerHTML = `<div class="card">
        <div class="chart-controls" id="analysis-cc">
            <select id="a-symbol" class="form-select" style="width:auto;padding:6px 12px;font-size:12px;">
                <option value="ETHUSDT">ETH/USDT</option>
                <option value="BTCUSDT">BTC/USDT</option>
                <option value="BNBUSDT">BNB/USDT</option>
            </select>
            ${tfButtons('1h', 'changeAnalysisTf')}
            <div class="chart-divider"></div>
            <button class="ind-btn" onclick="toggleIndicator('ema',this)">EMA</button>
            <button class="ind-btn" onclick="toggleIndicator('sar',this)">SAR</button>
        </div>
        <div id="analysis-chart" style="width:100%;height:600px;"></div>
    </div>`;

    makeChart('analysis-chart', 600);
    loadChartData('ETHUSDT', '1h');

    document.getElementById('a-symbol').addEventListener('change', () => {
        const tf = document.querySelector('#analysis-cc .tf-btn.active')?.textContent || '1h';
        makeChart('analysis-chart', 600);
        loadChartData(document.getElementById('a-symbol').value, tf);
    });
}

function changeAnalysisTf(tf, btn) {
    btn.closest('.chart-controls').querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    makeChart('analysis-chart', 600);
    loadChartData(document.getElementById('a-symbol').value, tf);
}
