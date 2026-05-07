/* Vitamin Checker - Frontend Application */
(function() {
    'use strict';

    const VITAMIN_SOURCES = {
        "A":   {emoji: "🥕", foods: "Carottes, patate douce, épinards, melon, abricot"},
        "B1":  {emoji: "🌾", foods: "Porc, céréales complètes, lentilles, noix"},
        "B2":  {emoji: "🥛", foods: "Lait, yaourt, fromage, amandes, épinards"},
        "B3":  {emoji: "🍗", foods: "Poulet, thon, cacahuètes, champignons"},
        "B5":  {emoji: "🥑", foods: "Avocat, champignons, poulet, œufs"},
        "B6":  {emoji: "🐟", foods: "Saumon, thon, poulet, banane, pistache"},
        "B9":  {emoji: "🥬", foods: "Épinards, lentilles, haricots, asperges, avocat"},
        "B12": {emoji: "🥩", foods: "Sardines, saumon, bœuf, fromage, œufs"},
        "C":   {emoji: "🍊", foods: "Kiwi, poivron, orange, fraise, brocoli"},
        "D":   {emoji: "☀️", foods: "Saumon, sardines, maquereau, œufs, lait"},
        "E":   {emoji: "🌻", foods: "Amandes, huile de tournesol, noisettes, avocat"},
        "K":   {emoji: "🥗", foods: "Épinards, brocoli, chou, salade, kiwi"},
    };

    const VITAMINS = {
        "A":   {"name": "Vitamin A",   "unit": "µg",  "rda": 900,   "color": "#e74c3c"},
        "B1":  {"name": "Vitamin B1",  "unit": "mg",  "rda": 1.2,   "color": "#e67e22"},
        "B2":  {"name": "Vitamin B2",  "unit": "mg",  "rda": 1.3,   "color": "#f1c40f"},
        "B3":  {"name": "Vitamin B3",  "unit": "mg",  "rda": 16,    "color": "#2ecc71"},
        "B5":  {"name": "Vitamin B5",  "unit": "mg",  "rda": 5,     "color": "#1abc9c"},
        "B6":  {"name": "Vitamin B6",  "unit": "mg",  "rda": 1.7,   "color": "#3498db"},
        "B9":  {"name": "Vitamin B9",  "unit": "µg",  "rda": 400,   "color": "#9b59b6"},
        "B12": {"name": "Vitamin B12", "unit": "µg",  "rda": 2.4,   "color": "#8e44ad"},
        "C":   {"name": "Vitamin C",   "unit": "mg",  "rda": 90,    "color": "#e91e63"},
        "D":   {"name": "Vitamin D",   "unit": "µg",  "rda": 20,    "color": "#ff9800"},
        "E":   {"name": "Vitamin E",   "unit": "mg",  "rda": 15,    "color": "#4caf50"},
        "K":   {"name": "Vitamin K",   "unit": "µg",  "rda": 120,   "color": "#009688"},
    };

    let radarChart = null;
    let barChart = null;
    let selectedFile = null;

    // ─── DOM References ──────────────────────────────────────────────
    const uploadZone = document.getElementById('uploadZone');
    const imageInput = document.getElementById('imageInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const clearBtn = document.getElementById('clearBtn');
    const previewContainer = document.getElementById('previewContainer');
    const previewImage = document.getElementById('previewImage');
    const previewName = document.getElementById('previewName');
    const previewSize = document.getElementById('previewSize');

    // ─── Event Listeners ─────────────────────────────────────────────
    uploadZone.addEventListener('click', (e) => {
        if (e.target === imageInput) return;
        imageInput.click();
    });

    analyzeBtn.addEventListener('click', analyzeReceipt);
    clearBtn.addEventListener('click', clearAll);

    imageInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    // ─── Functions ───────────────────────────────────────────────────
    function handleFile(file) {
        if (!file.type.startsWith('image/') && !file.type.endsWith('pdf')) {
            showError('Please select an image (JPG, PNG) or PDF file.');
            return;
        }

        selectedFile = file;

        const reader = new FileReader();
        reader.onload = (e) => {
            previewImage.src = e.target.result;
            previewContainer.classList.add('active');
        };
        reader.readAsDataURL(file);

        previewName.textContent = file.name;
        previewSize.textContent = (file.size / 1024).toFixed(1) + ' KB';

        uploadZone.classList.add('has-file');
        uploadZone.querySelector('.upload-icon').textContent = '✅';
        uploadZone.querySelector('.upload-title').textContent = 'Photo loaded: ' + file.name;
        uploadZone.querySelector('.upload-text').textContent = 'Click to change the photo';

        analyzeBtn.disabled = false;
        clearBtn.style.display = 'inline-flex';

        document.getElementById('results').style.display = 'none';
        document.getElementById('errorMsg').style.display = 'none';
    }

    function clearAll() {
        selectedFile = null;
        imageInput.value = '';
        previewContainer.classList.remove('active');
        previewImage.src = '';
        previewName.textContent = '';
        previewSize.textContent = '';
        uploadZone.classList.remove('has-file');
        uploadZone.querySelector('.upload-icon').textContent = '📷';
        uploadZone.querySelector('.upload-title').textContent = 'Drop your photo here or click to browse';
        uploadZone.querySelector('.upload-text').textContent = 'Supports JPG, PNG, PDF';
        analyzeBtn.disabled = true;
        clearBtn.style.display = 'none';
        document.getElementById('results').style.display = 'none';
        document.getElementById('errorMsg').style.display = 'none';
        if (radarChart) { radarChart.destroy(); radarChart = null; }
        if (barChart) { barChart.destroy(); barChart = null; }
    }

    async function analyzeReceipt() {
        if (!selectedFile) {
            showError('Please upload a photo of your grocery receipt.');
            return;
        }

        document.getElementById('loading').classList.add('active');
        document.getElementById('results').style.display = 'none';
        document.getElementById('errorMsg').style.display = 'none';
        analyzeBtn.disabled = true;

        try {
            const formData = new FormData();
            formData.append('receipt_image', selectedFile);
            const response = await fetch('analyze', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            if (!response.ok) {
                showError(data.error || "An error occurred during analysis.");
                return;
            }
            renderResults(data);
        } catch (err) {
            showError("Server connection error.");
        } finally {
            document.getElementById('loading').classList.remove('active');
            analyzeBtn.disabled = false;
        }
    }

    function showError(msg) {
        const el = document.getElementById('errorMsg');
        el.textContent = "❌ " + msg;
        el.style.display = 'block';
        document.getElementById('loading').classList.remove('active');
        analyzeBtn.disabled = false;
    }

    function renderResults(data) {
        document.getElementById('results').style.display = 'block';

        const deficitCount = Object.values(data.gaps).filter(g => g.status === 'deficit').length;
        const surplusCount = Object.values(data.gaps).filter(g => g.status === 'surplus').length;
        document.getElementById('statsRow').innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${data.total_items}</div>
                <div class="stat-label">Items scanned</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${data.matched_count}</div>
                <div class="stat-label">Matched products</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #f87171">${deficitCount}</div>
                <div class="stat-label">Deficiencies</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color: #4ade80">${surplusCount}</div>
                <div class="stat-label">Vitamins covered</div>
            </div>
        `;

        renderCharts(data.gaps);
        renderVitaminBars(data.gaps);
        renderAdvice(data.gaps);
        renderItems(data.matched_items);

        if (data.unmatched_items.length > 0) {
            document.getElementById('unmatchedCard').style.display = 'block';
            document.getElementById('unmatchedList').innerHTML =
                data.unmatched_items.map(i => `<span class="unmatched-tag">${i}</span>`).join('');
        } else {
            document.getElementById('unmatchedCard').style.display = 'none';
        }

        document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
    }

    function renderCharts(gaps) {
        const labels = Object.values(gaps).map(g => g.name);
        const coverages = Object.values(gaps).map(g => Math.min(g.coverage, 150));
        const colors = Object.values(gaps).map(g => g.status === 'surplus' ? 'rgba(74,222,128,0.7)' : 'rgba(248,113,113,0.7)');

        if (radarChart) radarChart.destroy();
        if (barChart) barChart.destroy();

        const radarCtx = document.getElementById('radarChart').getContext('2d');
        radarChart = new Chart(radarCtx, {
            type: 'radar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Coverage %',
                    data: coverages,
                    backgroundColor: 'rgba(56,189,248,0.15)',
                    borderColor: 'rgba(56,189,248,0.8)',
                    borderWidth: 2,
                    pointBackgroundColor: colors,
                    pointBorderColor: '#fff',
                    pointRadius: 5,
                }, {
                    label: 'RDA (100%)',
                    data: Array(labels.length).fill(100),
                    backgroundColor: 'rgba(255,255,255,0.03)',
                    borderColor: 'rgba(255,255,255,0.2)',
                    borderWidth: 1,
                    borderDash: [5, 5],
                    pointRadius: 0,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 150,
                        grid: { color: 'rgba(255,255,255,0.06)' },
                        angleLines: { color: 'rgba(255,255,255,0.06)' },
                        ticks: {
                            color: '#94a3b8',
                            backdropColor: 'transparent',
                            stepSize: 25,
                        },
                        pointLabels: { color: '#e2e8f0', font: { size: 11 } }
                    }
                },
                plugins: {
                    legend: { labels: { color: '#94a3b8' } },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                const key = Object.keys(gaps)[ctx.dataIndex];
                                const g = gaps[key];
                                return g.name + ': ' + g.coverage + '% of RDA';
                            }
                        }
                    }
                }
            }
        });

        const deficitData = Object.values(gaps).map(g => g.gap);
        const barCtx = document.getElementById('barChart').getContext('2d');
        barChart = new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Gap %',
                    data: deficitData,
                    backgroundColor: colors,
                    borderColor: colors.map(c => c.replace('0.7', '1')),
                    borderWidth: 1,
                    borderRadius: 6,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                scales: {
                    x: {
                        beginAtZero: true,
                        max: 100,
                        title: { display: true, text: 'Deficiency %', color: '#94a3b8' },
                        grid: { color: 'rgba(255,255,255,0.06)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#e2e8f0', font: { size: 11 } }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                const key = Object.keys(gaps)[ctx.dataIndex];
                                const g = gaps[key];
                                if (g.status === 'surplus') return '✅ Covered';
                                return '🔴 Missing ' + g.gap + '% of RDA (' + g.rda + ' ' + g.unit + '/day)';
                            }
                        }
                    }
                }
            }
        });
    }

    function renderVitaminBars(gaps) {
        const container = document.getElementById('vitaminBars');
        container.innerHTML = '';

        for (const [key, g] of Object.entries(gaps)) {
            const barWidth = Math.min(g.coverage, 100);
            const isDeficit = g.status === 'deficit';

            const row = document.createElement('div');
            row.className = 'vit-row';
            row.innerHTML = `
                <div class="vit-name" style="color: ${g.color}">${g.name}</div>
                <div class="vit-bar-container">
                    <div class="vit-bar ${g.status}" style="width: ${barWidth}%; background: ${g.color}"></div>
                </div>
                <div class="vit-pct" style="color: ${isDeficit ? '#f87171' : '#4ade80'}">${g.coverage}%</div>
                <div class="vit-gap">
                    <span class="gap-badge ${g.status}">
                        ${isDeficit ? '🔴 -' + g.gap + '%' : '✅ OK'}
                    </span>
                </div>
            `;
            container.appendChild(row);
        }
    }

    function renderAdvice(gaps) {
        const container = document.getElementById('adviceGrid');
        container.innerHTML = '';

        const deficits = Object.entries(gaps).filter(([k, g]) => g.status === 'deficit');

        if (deficits.length === 0) {
            container.innerHTML = '<p style="color: var(--success)">🎉 Great! Your groceries cover all essential vitamins!</p>';
            return;
        }

        for (const [key, g] of deficits) {
            const src = VITAMIN_SOURCES[key] || {emoji: "🥗", foods: "Varied foods"};
            const card = document.createElement('div');
            card.className = 'advice-card';
            card.innerHTML = `
                <h4 style="color: ${g.color}">${src.emoji} ${g.name}</h4>
                <p>Missing <strong>${g.gap}%</strong> of daily recommended intake (${g.rda} ${g.unit}/day)</p>
                <p style="margin-top: 0.5rem; color: var(--accent);">💡 Buy next time: <strong>${src.foods}</strong></p>
            `;
            container.appendChild(card);
        }
    }

    function renderItems(items) {
        const container = document.getElementById('itemsList');
        container.innerHTML = '';

        for (const item of items) {
            const chip = document.createElement('div');
            chip.className = 'item-chip';

            const vitTags = Object.entries(item.vitamins).map(([k, v]) => {
                const color = VITAMINS[k] ? VITAMINS[k].color : '#888';
                const name = VITAMINS[k] ? VITAMINS[k].name : k;
                return `<span class="vit-tag" style="background: ${color}">${name} ${v}%</span>`;
            }).join('');

            chip.innerHTML = `
                <div class="item-name">🛒 ${item.item} <small style="color:var(--text-secondary)">→ ${item.matched_as}</small></div>
                <div class="item-vits">${vitTags}</div>
            `;
            container.appendChild(chip);
        }
    }
})();