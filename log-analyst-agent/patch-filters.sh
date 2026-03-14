#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Patching the files the container actually uses..."

PY="dashboard.py"
HTML="templates/dashboard.html"
BACKUP=".bak.$(date +%s)"

# Sanity checks
[[ -f "$PY" ]] || { echo "❌ Missing $PY in $(pwd)"; exit 1; }
[[ -f "$HTML" ]] || { echo "❌ Missing $HTML in $(pwd)"; exit 1; }

cp "$PY" "$PY$BACKUP"
cp "$HTML" "$HTML$BACKUP"
echo "📦 Backed up to $PY$BACKUP and $HTML$BACKUP"

# 1) Add classifier (only if not already present)
if ! grep -q "def classify_log_source" "$PY"; then
cat >> "$PY" <<'EOF'


def classify_log_source(report: dict) -> str:
    analysis = (report.get("analysis") or "").lower()

    appgate_terms = [
        "appgate",
        "sdp",
        "controller",
        "entitlement",
        "gateway",
        "connection timeout"
    ]

    palo_terms = [
        "palo alto",
        "pan-os",
        "panorama",
        "panw",
        "firewall",
        "threat",
        "denied traffic",
        "session end"
    ]

    if any(term in analysis for term in appgate_terms):
        return "appgate"
    if any(term in analysis for term in palo_terms):
        return "paloalto"
    return "general"
EOF
  echo "✅ Added classify_log_source()"
else
  echo "ℹ️ classify_log_source() already exists"
fi

# 2) Inject log_source into the /api/reports response
# We add it right after filename is set in the response dict if possible,
# otherwise we add it right after reports.append({ line.
if ! grep -q "\"log_source\"" "$PY"; then
  # Try to insert after 'filename': ...
  if grep -q "'filename':" "$PY"; then
    sed -i "/'filename':/a\            'log_source': classify_log_source(data)," "$PY"
    echo "✅ Injected log_source after filename"
  else
    sed -i "/reports\.append({/a\        'log_source': classify_log_source(data)," "$PY"
    echo "✅ Injected log_source after reports.append({"
  fi
else
  echo "ℹ️ log_source already present in $PY"
fi

# 3) Add buttons in HTML (only if not already there)
if ! grep -q "filterAppgate" "$HTML"; then
  # Insert a filters div near the Analysis Reports header
  sed -i "s|<h2>Analysis Reports</h2>|<h2>Analysis Reports</h2>\n<div class=\"filters\">\n  <button class=\"filter-btn active\" id=\"filterAll\" onclick=\"setFilter('all')\">All Logs</button>\n  <button class=\"filter-btn\" id=\"filterAppgate\" onclick=\"setFilter('appgate')\">AppGate</button>\n  <button class=\"filter-btn\" id=\"filterPalo\" onclick=\"setFilter('paloalto')\">Palo Alto</button>\n</div>|" "$HTML"
  echo "✅ Added filter buttons"
else
  echo "ℹ️ Filter buttons already exist"
fi

# 4) Add CSS styles (append into <style> block)
if ! grep -q ".filter-btn" "$HTML"; then
  sed -i "/<\/style>/i\
.filters { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.5rem; }\
.filter-btn { background: #edf2f7; color: #2d3748; border: 1px solid #e2e8f0; padding: 0.45rem 0.75rem; border-radius: 999px; cursor: pointer; font-size: 0.8rem; font-weight: 600; }\
.filter-btn:hover { background: #e2e8f0; }\
.filter-btn.active { background: #667eea; color: white; border-color: #667eea; }\
" "$HTML"
  echo "✅ Added filter button CSS"
else
  echo "ℹ️ Filter button CSS already present"
fi

# 5) Add JS filtering logic + hook loadReports()
if ! grep -q "let currentFilter" "$HTML"; then
  sed -i "/<script>/a\
let allReports = [];\nlet currentFilter = 'all';\n\nfunction getFilteredReports() {\n  if (currentFilter === 'all') return allReports;\n  return allReports.filter(r => r.log_source === currentFilter);\n}\n\nfunction setFilter(filter) {\n  currentFilter = filter;\n  ['filterAll','filterAppgate','filterPalo'].forEach(id => document.getElementById(id)?.classList.remove('active'));\n  if (filter === 'all') document.getElementById('filterAll')?.classList.add('active');\n  if (filter === 'appgate') document.getElementById('filterAppgate')?.classList.add('active');\n  if (filter === 'paloalto') document.getElementById('filterPalo')?.classList.add('active');\n  renderReports(getFilteredReports());\n}\n" "$HTML"
  echo "✅ Injected JS filter logic"
else
  echo "ℹ️ JS filter logic already present"
fi

# Hook into loadReports(): replace renderReports(reports) with cached + filtered render
# Do not fail if pattern differs.
sed -i "s/renderReports(reports);/allReports = reports;\n    renderReports(getFilteredReports());/g" "$HTML" || true

echo "✅ Hooked loadReports to use filtering"

echo "🚀 Rebuilding + restarting containers to apply changes..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo "✅ Done. Quick verification:"
echo "curl -s http://localhost:5000/api/reports | grep -o '\"log_source\":\"[^\"]*\"' | head"
