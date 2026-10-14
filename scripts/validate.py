"""Exercise the original KISDI code without changing project files."""
import argparse
import os
from pathlib import Path
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path('/workspace/KISDI_Classifier')
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument('--models', action='store_true', help='Also run original BERT inference; needs the Hugging Face cache or allowed network.')
args = parser.parse_args()

import pandas as pd
import torch
import kss
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import processing_model_all
from function.keyword_finder_v5 import keyword_finder
from function.find_app_down_v2 import app_finder

frame = pd.read_csv('분류필요데이터/preprocessed_website_url.csv', encoding='cp949')
assert len(frame) > 0 and {'사업체명', '홈페이지1'} <= set(frame.columns)
print('PASS: input CSV (%d rows)' % len(frame), flush=True)
parts = kss.split_sentences('중개자는 거래 당사자가 아닙니다. 판매자가 책임을 집니다.', num_workers=1)
assert len(parts) == 2
print('PASS: Korean sentence splitting', flush=True)
image = Image.new('RGB', (1200, 160), 'white')
font = ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc', 64, index=1)
ImageDraw.Draw(image).text((20, 20), '사업자등록번호 통신판매 중개자', font=font, fill='black')
ocr = pytesseract.image_to_string(image, lang='kor', config='--psm 7')
assert '사업자등록번호' in ocr.replace(' ', '')
print('PASS: Korean OCR', flush=True)
for category in (201, 202, 203):
    weights = torch.load('필요파일/classifier-kor-base_%d.pth' % category, map_location='cpu', weights_only=True)
    assert tuple(weights['classifier.weight'].shape) == (2, 768)
    assert all(torch.isfinite(value).all() for value in weights.values())
    del weights
    print('PASS: checkpoint integrity %d' % category, flush=True)

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
url = 'http://127.0.0.1:%d/' % server.server_port
try:
    for category, dictionary, platform in (
        (201, 'keyword_dict_201.pickle', None),
        (202, 'keyword_dict2.pickle', 'platform2.pickle'),
        (203, 'keyword_dict_203.pickle', None),
    ):
        worker = keyword_finder('필요파일/' + dictionary, '필요파일/' + platform if platform else None, category)
        try:
            result = worker.main_processer('클라우드 검증', url)
            assert result[0] == '1234567890' and result[1] == str(category), result
        finally:
            worker.driver.quit()
        print('PASS: real browser keyword classification %d' % category, flush=True)
    worker = app_finder()
    try:
        assert worker.finding('클라우드 검증', url)[1] == 'download_url'
    finally:
        worker.driver.quit()
    print('PASS: real browser app-link detection', flush=True)
finally:
    server.shutdown()
    server.server_close()

results = Path('/workspace/.kisdi/results')
results.mkdir(exist_ok=True)
examples = sorted(Path('/workspace/kisdi-assets/KISDI_classifier_update/시험 결과 파일').glob('*.xlsx'))
assert len(examples) == 3
for original in examples:
    data = pd.read_excel(original)
    assert len(data) > 0 and {'cate', 'keyword'} <= set(data.columns)
    output = results / original.name
    data.to_excel(output, index=False)
    pd.testing.assert_frame_equal(data, pd.read_excel(output))
print('PASS: three reference Excel read/write round trips', flush=True)

if args.models:
    from function.bert_classifier import term_predictor
    for category in (201, 202, 203):
        predictor = term_predictor('klue/roberta-base', '필요파일/classifier-kor-base_%d.pth' % category)
        prediction = predictor.predict('회사는 통신판매 중개자로서 거래 당사자가 아니며 판매자가 계약의 책임을 집니다.')
        assert prediction in (0, 1)
        print('PASS: original BERT inference %d -> %d' % (category, prediction), flush=True)
        del predictor
else:
    print('UNRUN: original BERT inference (add --models after Hugging Face access is available)', flush=True)
