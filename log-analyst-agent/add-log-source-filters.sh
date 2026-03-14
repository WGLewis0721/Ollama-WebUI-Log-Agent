#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Applying log-source filter update..."

### -------- CONFIG --------
DASHBOARD_PY="agent/dashboard.py"
DASHBOARD_HTML="agent/templates/dashboard.html"
BACKUP_SUFFIX=".bak.$(date +%s)"
### ------------------------

# Safety backups
cp "$DASHBOARD_PY" "$DASHBOARD_PY$BACKUP_SUFFIX"
cp "$DASHBOARD_HTML" "$DASHBOARD_HTML$BACKUP_SUFFIX"

echo "📦 Backups created"

# -------------------------
# 1. Backend: classifier
# -------------------------
if ! grep -q "def classify_log_source" "$DASHBOARD_PY"; then
  cat >> "$DASHBOARD_PY" << 'EOF'

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
  echo "✅ Backend classifier added"
else
  echo "ℹ️ Backend classifier already present"
fi

# Inject log_source into report summary
if ! grep -q "log_source" "$DASHBOARD_PY"; then
  sed -i \
    "/reports.append({/a\        'log_source': classify_log_source(data)," \
    "$DASHBOARD_PY"
  echo "✅ log_source field injected"
else
  echo "ℹ️ log_source already injected"
fi

# -------------------------
# 2. Frontend: buttons
# -------------------------
if ! grep -q "filterAppgate" "$DASHBOARD_HTML"; then
  sed -i \
    "s|<h2>Analysis Reports</h2>|<h2>Analysis Reports</h2>\n<div class=\"filters\">\n  <button class=\"filter-btn active\" id=\"filterAll\" onclick=\"setFilter('all')\">All Logs</button>\n  <button class=\"filter-btn\" id=\"filterAppgate\" onclick=\"setFilter('appgate')\">AppGate</button>\n  <button class=\"filter-btn\" id=\"filterPalo\" onclick=\"setFilter('paloalto')\">Palo Alto</button>\n</div>|" \
    "$DASHBOARD_HTML"

  echo "✅ Filter buttons added"
else
  echo "ℹ️ Filter buttons already exist"
fi

# -------------------------
# 3. Frontend: JS logic
# -------------------------
if ! grep -q "currentFilter" "$DASHBOARD_HTML"; then
  sed -i \
    "/<script>/a\let allReports = [];\nlet currentFilter = 'all';\n\nfunction getFilteredReports() {\n  if (currentFilter === 'all') return allReports;\n  return allReports.filter(r => r.log_source === currentFilter);\n}\n\nfunction setFilter(filter) {\n  currentFilter = filter;\n  ['filterAll','filterAppgate','filterPalo'].forEach(id => document.getElementById(id)?.classList.remove('active'));\n  if (filter === 'all') filterAll.classList.add('active');\n  if (filter === 'appgate') filterAppgate.classList.add('active');\n  if (filter === 'paloalto') filterPalo.classList.add('active');\n  renderReports(getFilteredReports());\n}\n" \
    "$DASHBOARD_HTML"

  echo "✅ JS filter logic injected"
else
  echo "ℹ️ JS filter logic already present"
fi

# -------------------------
# 4. Hook into loadReports
# -------------------------
sed -i \
  "s/renderReports(reports);/allReports = reports;\n  renderReports(getFilteredReports());/" \
  "$DASHBOARD_HTML" || true

echo "🎯 loadReports hook updated"

# -------------------------
# Done
# -------------------------
echo "🚀 Update complete"
echo "➡ Restart the app:"
echo "   docker compose restart   OR"
echo "   CTRL+C && python agent/dashboard.py"
