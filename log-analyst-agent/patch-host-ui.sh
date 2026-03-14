#!/usr/bin/env bash
set -euo pipefail

PY="agent/dashboard.py"
HTML="agent/templates/dashboard.html"

[[ -f "$PY" ]] || { echo "Missing $PY"; exit 1; }
[[ -f "$HTML" ]] || { echo "Missing $HTML"; exit 1; }

cp "$PY" "$PY.bak.$(date +%s)"
cp "$HTML" "$HTML.bak.$(date +%s)"

# Add classifier if missing
if ! grep -q "def classify_log_source" "$PY"; then
cat >> "$PY" <<'EOF'


def classify_log_source(report: dict) -> str:
    analysis = (report.get("analysis") or "").lower()

    appgate_terms = [
        "appgate", "sdp", "controller", "entitlement", "gateway", "connection timeout"
    ]
    palo_terms = [
        "palo alto", "pan-os", "panorama", "panw", "firewall", "threat",
        "denied traffic", "session end"
    ]

    if any(t in analysis for t in appgate_terms):
        return "appgate"
    if any(t in analysis for t in palo_terms):
        return "paloalto"
    return "general"
EOF
fi

# Inject log_source into reports.append({ ... })
if ! grep -q "'log_source'" "$PY"; then
  awk '
    inserted==0 && $0 ~ /reports\.append\(\{/ {
      print $0
      print "                '\''log_source'\'': classify_log_source(data),"
      inserted=1
      next
    }
    { print }
  ' "$PY" > /tmp/dashboard.py && mv /tmp/dashboard.py "$PY"
fi

# Add filter buttons
if ! grep -q "filterAppgate" "$HTML"; then
  awk '
    $0 ~ /<h2>Analysis Reports<\/h2>/ {
      print $0
      print "<div class=\"filters\">"
      print "  <button class=\"filter-btn active\" id=\"filterAll\" onclick=\"setFilter('\''all'\'')\">All Logs</button>"
      print "  <button class=\"filter-btn\" id=\"filterAppgate\" onclick=\"setFilter('\''appgate'\'')\">AppGate</button>"
      print "  <button class=\"filter-btn\" id=\"filterPalo\" onclick=\"setFilter('\''paloalto'\'')\">Palo Alto</button>"
      print "</div>"
      next
    }
    { print }
  ' "$HTML" > /tmp/dashboard.html && mv /tmp/dashboard.html "$HTML"
fi

# Add CSS
if ! grep -q "\.filter-btn" "$HTML"; then
  awk '
    $0 ~ /<\/style>/ {
      print ".filters { display:flex; gap:0.5rem; align-items:center; margin-bottom:0.5rem; }"
      print ".filter-btn { background:#edf2f7; color:#2d3748; border:1px solid #e2e8f0; padding:0.45rem 0.75rem; border-radius:999px; cursor:pointer; font-size:0.8rem; font-weight:600; }"
      print ".filter-btn:hover { background:#e2e8f0; }"
      print ".filter-btn.active { background:#667eea; color:#fff; border-color:#667eea; }"
      print $0
      next
    }
    { print }
  ' "$HTML" > /tmp/dashboard.html && mv /tmp/dashboard.html "$HTML"
fi

# Add JS filter logic
if ! grep -q "let currentFilter" "$HTML"; then
  awk '
    $0 ~ /<script>/ {
      print $0
      print "let allReports = [];"
      print "let currentFilter = \"all\";"
      print "function getFilteredReports(){"
      print "  if(currentFilter === \"all\") return allReports;"
      print "  return allReports.filter(r => r.log_source === currentFilter);"
      print "}"
      print "function setFilter(filter){"
      print "  currentFilter = filter;"
      print "  [\"filterAll\",\"filterAppgate\",\"filterPalo\"].forEach(id => document.getElementById(id)?.classList.remove(\"active\"));"
      print "  if(filter === \"all\") document.getElementById(\"filterAll\")?.classList.add(\"active\");"
      print "  if(filter === \"appgate\") document.getElementById(\"filterAppgate\")?.classList.add(\"active\");"
      print "  if(filter === \"paloalto\") document.getElementById(\"filterPalo\")?.classList.add(\"active\");"
      print "  renderReports(getFilteredReports());"
      print "}"
      next
    }
    { print }
  ' "$HTML" > /tmp/dashboard.html && mv /tmp/dashboard.html "$HTML"
fi

# Hook loadReports
if grep -q "renderReports(reports);" "$HTML" && ! grep -q "allReports = reports;" "$HTML"; then
  sed -i 's/renderReports(reports);/allReports = reports;\n    renderReports(getFilteredReports());/' "$HTML"
fi

echo "OK"
