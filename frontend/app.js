/**
 * Smart City Emergency Dispatch — Complete Control Center UI
 */

const API_BASE = ''; 

// UI Elements
const $input = document.getElementById('transcript-input');
const $dispatchBtn = document.getElementById('dispatch-btn');
const $reasoningBox = document.getElementById('cot-content');
const $cotBox = document.getElementById('cot-box');
const $cotToggle = document.getElementById('cot-toggle');
const $incidentList = document.getElementById('incident-list');
const $incidentCount = document.getElementById('stat-incidents');
const $callCount = document.getElementById('stat-calls');
const $resetBtn = document.getElementById('reset-btn');

const PRESET_DATA = {
    "fire1": "There is a huge fire at City Mall on Main Street, people are trapped inside the building!",
    "fire2": "I'm calling from the West entrance of the Mall, there is smoke everywhere and a major structure fire!",
    "medical": "Someone just collapsed near the Pharmacy on Oak Avenue, they aren't breathing!",
    "fire3": "Main Street Mall is on fire, we need help now!",
    "gas": "I smell a strong gas leak near the food court at the City Mall."
};

// ─── INITIALIZATION ───
window.addEventListener('load', () => {
    console.log("🚀 Dashboard Initialized.");
    updateIncidents();
    setInterval(updateIncidents, 3000); 
    setInterval(updateClock, 1000);
    updateClock();
});

function updateClock() {
    const $clock = document.getElementById('clock');
    if ($clock) $clock.textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}

// ─── COT TOGGLE ───
if ($cotToggle) {
    $cotToggle.addEventListener('click', () => {
        $reasoningBox.classList.toggle('collapsed');
        $cotToggle.querySelector('.cot-chevron').style.transform = 
            $reasoningBox.classList.contains('collapsed') ? 'rotate(0deg)' : 'rotate(180deg)';
    });
}

// ─── PRESETS ───
document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const presetKey = btn.getAttribute('data-preset');
        if ($input) {
            $input.value = PRESET_DATA[presetKey] || "";
            $dispatchBtn.disabled = false;
        }
    });
});

if ($input) {
    $input.addEventListener('input', () => {
        $dispatchBtn.disabled = $input.value.trim().length === 0;
    });
}

// ─── DISPATCH ───
$dispatchBtn.addEventListener('click', async () => {
    const transcript = $input.value.trim();
    if (!transcript) return;

    $dispatchBtn.disabled = true;
    const btnText = $dispatchBtn.querySelector('.btn-text');
    const originalText = btnText.innerText;
    btnText.innerText = 'Analyzing...';

    try {
        const res = await fetch(`${API_BASE}/process-call`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript })
        });
        const data = await res.json();

        if ($cotBox) {
            $cotBox.classList.remove('hidden');
            $reasoningBox.classList.remove('collapsed');
            renderReasoning(data.chain_of_thought, data.is_duplicate);
        }
        
        await updateIncidents();
        $input.value = '';
    } catch (err) {
        console.error("Dispatch failed:", err);
    } finally {
        $dispatchBtn.disabled = true;
        btnText.innerText = originalText;
    }
});

// ─── RESET ───
if ($resetBtn) {
    $resetBtn.addEventListener('click', async () => {
        if (!confirm("Clear all incidents?")) return;
        try {
            await fetch(`${API_BASE}/incidents/clear`, { method: 'DELETE' });
            window.location.reload();
        } catch (err) { console.error(err); }
    });
}

// ─── UPDATE BOARD ───
async function updateIncidents() {
    try {
        const res = await fetch(`${API_BASE}/incidents`);
        const data = await res.json();
        let incidents = data.incidents || [];
        
        // SORT BY PRIORITY
        incidents.sort((a, b) => {
            if (b.severity !== a.severity) return b.severity - a.severity;
            if (b.caller_count !== a.caller_count) return b.caller_count - a.caller_count;
            return new Date(a.timestamp) - new Date(b.timestamp);
        });

        if ($incidentCount) $incidentCount.textContent = incidents.length;
        if (!$incidentList) return;

        if (incidents.length === 0) {
            $incidentList.innerHTML = `<div class="empty-state"><h3>No Active Incidents</h3></div>`;
            if ($callCount) $callCount.textContent = '0';
            return;
        }

        let totalCalls = 0;
        $incidentList.innerHTML = incidents.map((inc, index) => {
            totalCalls += (inc.caller_count || 1);
            const severityClass = `sev-${inc.severity || 1}`;
            const status = (inc.status || "active").toLowerCase();
            const rank = index + 1;
            
            const formatName = (str) => str.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

            // 1. Dept Reports
            let deptHtml = "";
            if (inc.department_reports) {
                const reports = Object.entries(inc.department_reports).map(([key, val]) => `
                    <div class="dept-pill ${key.includes('fire') ? 'fire' : key.includes('ems') ? 'ems' : 'police'}">
                        <span>${formatName(key)}: ${val.explosion_risk || val.casualties_count || 'Active'}</span>
                    </div>
                `).join('');
                deptHtml = `<div class="dept-reports"><p class="feed-label">✅ DEPT NOTIFIED:</p><div class="dept-grid">${reports}</div></div>`;
            }

            // 2. Dispatch Plan
            let planHtml = "";
            if (inc.dispatch_plan && inc.dispatch_plan.length > 0) {
                const units = inc.dispatch_plan.map(p => `
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem;">
                        <span><strong>${p.unit_id}</strong> (${formatName(p.resource_type)})</span>
                        <span style="color:var(--accent-primary)">ETA: ${p.eta}m</span>
                    </div>
                `).join('');
                planHtml = `<div class="dispatch-plan" style="margin-top:10px; padding:10px; background:rgba(0,0,0,0.2); border-radius:6px;">
                    <p class="feed-label" style="color:#4caf50;">🚀 LIVE DISPATCH PLAN:</p>${units}</div>`;
            }

            return `
                <div class="incident-card ${severityClass}">
                    <div class="card-header">
                        <div class="header-left-meta" style="display:flex; align-items:center; gap:10px;">
                            <span class="rank-badge" style="background:var(--accent-primary); color:white; padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:800;">PRIORITY #${rank}</span>
                            <span class="incident-id">${inc.incident_id}</span>
                        </div>
                        <div style="display:flex; flex-direction:column; align-items:flex-end;">
                            <span class="severity-badge">Level ${inc.severity}</span>
                            <span style="font-size:0.6rem; opacity:0.7;">Conf: ${Math.round((inc.confidence || 0.9)*100)}%</span>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="info-row"><strong>📍 Location:</strong> ${inc.location}</div>
                        <div class="info-row"><strong>📞 Callers:</strong> ${inc.caller_count} | ⚖️ Rank ${rank}</div>
                        
                        ${inc.stacked_insight ? `<div class="stacked-insight"><strong>📝 COMMANDER SUMMARY:</strong> ${inc.stacked_insight}</div>` : ''}

                        ${deptHtml}
                        ${planHtml}
                        ${inc.escalated ? `<div style="background:#ef4444; color:white; padding:4px 10px; border-radius:4px; font-weight:900; font-size:0.7rem; margin-top:8px; text-align:center; animation: pulse 1s infinite;">🚨 ESCALATED</div>` : ''}

                        <div class="resource-tags" style="margin-top:12px;">
                            ${(inc.required_resources || []).map(r => `<span class="tag">${formatName(r)}</span>`).join('')}
                        </div>
                    </div>
                    <div class="card-footer">
                        Status: <span class="status-badge status-${status}">${status.toUpperCase()}</span>
                    </div>
                </div>
            `;
        }).join('');
        if ($callCount) $callCount.textContent = totalCalls;
    } catch (err) { console.error("Poll failed:", err); }
}

function renderReasoning(cot, isDuplicate) {
    if (!cot) return;
    $reasoningBox.innerHTML = `<div style="padding:10px;border-left:2px solid var(--accent-primary);background:rgba(255,255,255,0.03);">
        <strong style="color:${isDuplicate ? '#ff9800' : '#4caf50'}">${isDuplicate ? '🔄 MERGED' : '✨ NEW'}</strong>
        <p style="font-size:0.85rem; opacity:0.8; margin-top:5px;">${cot.replace(/\n/g, '<br>')}</p>
    </div>`;
}
