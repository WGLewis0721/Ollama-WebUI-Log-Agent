#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, send_file, request
from flask_cors import CORS
from pathlib import Path
import json, subprocess, threading, os
from datetime import datetime

app = Flask(__name__)
CORS(app)
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', '/app/output'))
analysis_running = False

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/reports')
def get_reports():
    reports = []
    for json_file in sorted(OUTPUT_DIR.glob('analysis_*.json'), reverse=True):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            txt_file = json_file.with_suffix('.txt')
            reports.append({
                'id': json_file.stem,
                'filename': json_file.name,
                'timestamp': data.get('generated', data.get('timestamp', '')),
                'analysis_type': data.get('analysis_type', 'general'),
                'model': data.get('model', 'Unknown'),
                'log_lines': data.get('log_lines', 0),
                'rag_enabled': data.get('rag_enabled', False),
                'has_error': 'error' in data,
                'metadata': data.get('metadata', {}),
                'txt_file': txt_file.name if txt_file.exists() else None
            })
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
    return jsonify(reports)

@app.route('/api/report/<report_id>')
def get_report(report_id):
    json_file = OUTPUT_DIR / f"{report_id}.json"
    if not json_file.exists():
        return jsonify({'error': 'Report not found'}), 404
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        if 'generated' in data and 'timestamp' not in data:
            data['timestamp'] = data['generated']
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/report/<report_id>/download')
def download_report(report_id):
    txt_file = OUTPUT_DIR / f"{report_id}.txt"
    if not txt_file.exists():
        return jsonify({'error': 'Report not found'}), 404
    return send_file(txt_file, as_attachment=True)

@app.route('/api/stats')
def get_stats():
    total_reports = len(list(OUTPUT_DIR.glob('analysis_*.json')))
    by_type = {}
    rag_count = 0
    recent_errors = 0
    for json_file in OUTPUT_DIR.glob('analysis_*.json'):
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            analysis_type = data.get('analysis_type', 'unknown')
            by_type[analysis_type] = by_type.get(analysis_type, 0) + 1
            if data.get('rag_enabled'):
                rag_count += 1
            if 'error' in data:
                recent_errors += 1
        except:
            pass
    return jsonify({
        'total_reports': total_reports,
        'by_type': by_type,
        'rag_count': rag_count,
        'recent_errors': recent_errors,
        'analysis_running': analysis_running
    })

@app.route('/api/latest')
def get_latest():
    json_files = sorted(OUTPUT_DIR.glob('analysis_*.json'), reverse=True)
    if not json_files:
        return jsonify({'error': 'No reports found'}), 404
    try:
        with open(json_files[0], 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trigger', methods=['POST'])
def trigger_analysis():
    global analysis_running
    if analysis_running:
        return jsonify({'status': 'already_running', 'message': 'Analysis already in progress'}), 409
    def run_analysis():
        global analysis_running
        analysis_running = True
        try:
            subprocess.run(['python', '-u', 'main_rag.py', '--once'], capture_output=True, timeout=600)
        except Exception as e:
            print(f"Trigger error: {e}")
        finally:
            analysis_running = False
    threading.Thread(target=run_analysis, daemon=True).start()
    return jsonify({'status': 'started', 'message': 'Analysis triggered successfully'})

@app.route('/api/trigger/status')
def trigger_status():
    return jsonify({'analysis_running': analysis_running})

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})



@app.route('/latest_query')
def latest_query():
    """Show the most recent query-mode result with raw OpenSearch query."""
    import json
    from pathlib import Path
    output_dir = os.getenv('OUTPUT_DIR', '/app/output')
    fpath = Path(output_dir) / 'latest_query.json'
    if not fpath.exists():
        return render_template_string("""
        <h2>No query results yet</h2>
        <p>Send a specific question to the agent via OpenWebUI first.</p>
        <p><a href="/">← Back to dashboard</a></p>
        """)
    data = json.loads(fpath.read_text())
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Latest Query Result</title>
<style>
body { font-family: monospace; margin: 40px; background: #0d1117; color: #c9d1d9; }
h1 { color: #58a6ff; }
h2 { color: #79c0ff; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 16px 0; }
pre { background: #0d1117; border: 1px solid #30363d; padding: 16px; border-radius: 6px;
      overflow-x: auto; color: #a5d6ff; font-size: 13px; white-space: pre-wrap; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         background: #1f6feb; color: white; font-size: 12px; margin: 2px; }
a { color: #58a6ff; }
.copy-btn { background: #238636; color: white; border: none; padding: 6px 12px;
            border-radius: 6px; cursor: pointer; float: right; font-size: 12px; }
</style>
</head>
<body>
<h1>🔍 Latest Query Result</h1>
<p><a href="/">← Dashboard</a></p>

<div class="card">
  <h2>Question</h2>
  <p>{{ data.user_question }}</p>
  <span class="badge">{{ data.total_hits }} hits</span>
  <span class="badge">{{ data.indices_searched }}</span>
</div>

<div class="card">
  <h2>AI Explanation</h2>
  <p style="white-space: pre-wrap; line-height: 1.6;">{{ data.explanation }}</p>
</div>

<div class="card">
  <h2>Generated OpenSearch Query
    <button class="copy-btn" onclick="copyQuery()">Copy</button>
  </h2>
  <p style="color:#8b949e; font-size:13px;">
    Verify in OpenSearch Dev Tools:<br>
    <code>POST /{{ data.indices_searched }}/_search</code>
  </p>
  <pre id="query-json">{{ query_json }}</pre>
</div>

{% if data.aggregations %}
<div class="card">
  <h2>Aggregation Results</h2>
  <pre>{{ aggs_json }}</pre>
</div>
{% endif %}

{% if data.sample_hits %}
<div class="card">
  <h2>Sample Log Entries ({{ data.sample_hits|length }})</h2>
  <pre>{{ hits_json }}</pre>
</div>
{% endif %}

<script>
function copyQuery() {
  navigator.clipboard.writeText(document.getElementById('query-json').textContent);
  document.querySelector('.copy-btn').textContent = 'Copied!';
  setTimeout(() => document.querySelector('.copy-btn').textContent = 'Copy', 2000);
}
</script>
</body>
</html>
""",
        data=data,
        query_json=json.dumps(data.get('generated_query', {}), indent=2),
        aggs_json=json.dumps(data.get('aggregations', {}), indent=2),
        hits_json=json.dumps(data.get('sample_hits', [])[:10], indent=2, default=str)
    )


if __name__ == '__main__':
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    port = int(os.getenv('DASHBOARD_PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
