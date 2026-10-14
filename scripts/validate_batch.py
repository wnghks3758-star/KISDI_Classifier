"""Run the original interactive CLI on a deterministic one-row local website."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
import signal
import subprocess
import threading
import pandas as pd

ROOT = Path('/workspace/KISDI_Classifier')
RESULTS = Path('/workspace/.kisdi/results')

class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        body = ('<!doctype html><html><head><title>KISDI 검증</title></head><body>'
                '사업자등록번호1234567890 광고 채용 매칭 통신판매중개자 웹툰 콘텐츠 '
                '<a href="https://play.google.com/store/apps/details?id=kisdi.smoke">앱 다운로드</a>'
                '</body></html>').encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *unused):
        pass

server = ThreadingHTTPServer(('127.0.0.1', 0), Page)
threading.Thread(target=server.serve_forever, daemon=True).start()
input_file = RESULTS / 'smoke-input.csv'
pd.DataFrame([{'사업체명': '클라우드 검증', '홈페이지1': 'http://127.0.0.1:%d/' % server.server_port}]).to_csv(input_file, index=False, encoding='cp949')
outputs = [RESULTS / ('smoke-%d.xlsx' % category) for category in (201, 202, 203)]
for path in outputs:
    if path.exists():
        path.unlink()
answers = '\n'.join(str(p) for p in [input_file] + outputs) + '\n'
child = None
try:
    with (RESULTS / 'batch-validation.log').open('w') as log:
        child = subprocess.Popen(
            ['/workspace/.kisdi/venv/bin/python', 'processing_model_all.py'],
            cwd=ROOT, stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
        child.communicate(answers, timeout=180)
        if child.returncode:
            raise SystemExit(child.returncode)
    for category, path in zip((201, 202, 203), outputs):
        assert path.exists(), path
        result = pd.read_excel(path)
        assert len(result) == 1, result.shape
        assert str(result.loc[0, 'cate']) == str(category), result.loc[0, 'cate']
        assert str(result.loc[0, '사업자등록번호']) == '1234567890'
        print('PASS: original CLI CSV -> category %d -> Excel (%d row)' % (category, len(result)), flush=True)
finally:
    if child is not None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        child.wait(timeout=10)
    server.shutdown()
    server.server_close()
