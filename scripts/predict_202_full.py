"""Resumable full-CSV inference using the original 202 classifier."""
import argparse
import csv
import fnmatch
import hashlib
import ipaddress
import json
import multiprocessing as mp
import os
from pathlib import Path
import re
import signal
import sqlite3
import sys
import time
from urllib.parse import urlsplit

ROOT = Path('/workspace/KISDI_Classifier')
ALLOW_LOOPBACK = False


def target_host(raw):
    if not isinstance(raw, str) or not raw.strip() or raw.strip().lower() == 'nan':
        return None
    try:
        url = raw.strip() if '://' in raw else 'https://' + raw.strip()
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or parsed.username or parsed.password:
            return None
        host = parsed.hostname.encode('idna').decode('ascii').lower().rstrip('.')
        if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', host):
            return None
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global and not (ALLOW_LOOPBACK and address.is_loopback):
            return None
        return host
    except (ValueError, UnicodeError, AttributeError):
        return None


def permitted(host, allowlist):
    return host in ('localhost', '127.0.0.1') or any(
        rule == '*' or host == rule or (rule.startswith('*.') and fnmatch.fnmatch(host, rule))
        for rule in allowlist
    )


def worker(pipe):
    os.setsid()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    import requests
    import torch
    from processing_model_202 import classifier
    from function.keyword_finder_v5 import keyword_finder
    from function.bert_classifier import term_predictor
    from function.find_app_down_v2 import app_finder

    torch.set_num_threads(1)
    predictor = term_predictor('klue/roberta-base', '필요파일/classifier-kor-base_202.pth')
    predictor.model.eval()
    pipe.send(('ready',))
    while True:
        task = pipe.recv()
        if task is None:
            return
        index, name, homepage = task
        started = time.monotonic()
        finder = app = None
        try:
            url = homepage if homepage.startswith(('http://', 'https://')) else 'https://' + homepage
            # A denied page must not become a negative classification.
            with requests.get(url, stream=True, timeout=(10, 30)) as response:
                response.raise_for_status()
            finder = keyword_finder('필요파일/keyword_dict2.pickle', '필요파일/platform2.pickle', 202)
            app = app_finder()
            with torch.no_grad():
                bizno, category, keyword = classifier(name, homepage, finder, predictor, app)
            status = 'ok' if category not in ('오류', 'URL 없음', None) else 'classification_error'
            for browser in (finder.driver, app.driver):
                browser.switch_to.default_content()
                if browser.current_url.startswith(('http://', 'https://')) and browser.execute_script('return document.documentURI').startswith('chrome-error:'):
                    status, category, keyword = 'browser_access_error', None, None
            result = (index, status, bizno, category, keyword, '', time.monotonic() - started)
        except requests.exceptions.ProxyError:
            result = (index, 'network_blocked', None, None, None, 'ProxyError', time.monotonic() - started)
        except requests.exceptions.HTTPError as error:
            result = (index, 'site_http_error', None, None, None, 'HTTP %d' % error.response.status_code, time.monotonic() - started)
        except Exception as error:
            result = (index, 'error', None, None, None, type(error).__name__, time.monotonic() - started)
        finally:
            for obj in (finder, app):
                if obj is not None:
                    try:
                        obj.driver.quit()
                    except Exception:
                        pass
        pipe.send(('result', result))


def stop_worker(slot):
    process = slot['process']
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    process.join(5)
    if process.is_alive():
        os.killpg(process.pid, signal.SIGKILL)
        process.join(5)
    slot['pipe'].close()


def start_worker(context):
    parent, child = context.Pipe()
    process = context.Process(target=worker, args=(child,))
    process.start()
    child.close()
    return {'process': process, 'pipe': parent, 'task': None, 'ready': False, 'started': time.monotonic()}


def export(db, rows, output):
    import pandas as pd
    results = {r[0]: r[1:] for r in db.execute('SELECT * FROM results')}
    values = []
    for index, row in enumerate(rows):
        item = {'row_index': index, **row, 'status': 'pending', '사업자등록번호': None, 'cate': None, 'keyword': None, 'detail': '', 'elapsed_s': None}
        if index in results:
            status, bizno, category, keyword, detail, elapsed = results[index]
            item.update(status=status, 사업자등록번호=bizno, cate=category, keyword=keyword, detail=detail, elapsed_s=elapsed)
        values.append(item)
    frame = pd.DataFrame(values)
    frame.to_csv(output / '202-full-results.csv', index=False, encoding='utf-8-sig')
    frame.to_excel(output / '202-full-results.xlsx', index=False)


def main():
    global ALLOW_LOOPBACK
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / '분류필요데이터/preprocessed_website_url.csv')
    parser.add_argument('--output-dir', type=Path, default=Path('/workspace/.kisdi/results/202-full'))
    parser.add_argument('--allowlist', type=Path, default=Path('/workspace/.kisdi/202-current-network.json'))
    parser.add_argument('--workers', type=int, choices=(1, 2, 4), default=4)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--allow-loopback', action='store_true', help='Only for controlled local fixture validation.')
    args = parser.parse_args()
    ALLOW_LOOPBACK = args.allow_loopback
    rows = list(csv.DictReader(args.input.open(encoding='cp949')))
    if args.limit is not None:
        rows = rows[:args.limit]
    if not rows or not {'사업체명', '홈페이지1'} <= rows[0].keys():
        raise SystemExit('Input needs 사업체명 and 홈페이지1 columns.')
    allowlist = json.loads(args.allowlist.read_text())
    hosts = {target_host(row['홈페이지1']) for row in rows}
    hosts.discard(None)
    missing = sorted(host for host in hosts if not permitted(host, allowlist))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    audit = {'rows': len(rows), 'invalid_url_rows': sum(target_host(r['홈페이지1']) is None for r in rows), 'target_hosts': len(hosts), 'missing_allowed_hosts': missing}
    (args.output_dir / 'preflight.json').write_text(json.dumps(audit, indent=2))
    if missing:
        print('BLOCKED: %d rows need %d target hosts; %d hosts are absent from the supplied runtime allowlist.' % (len(rows), len(hosts), len(missing)), flush=True)
        print('No prediction was started. See %s' % (args.output_dir / 'preflight.json'), flush=True)
        return 2

    db = sqlite3.connect(str(args.output_dir / 'checkpoint.sqlite'))
    db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)')
    digest = hashlib.sha256(args.input.read_bytes() + str(args.limit).encode()).hexdigest()
    prior = db.execute('SELECT value FROM meta WHERE key="input_sha256"').fetchone()
    if prior and prior[0] != digest:
        raise SystemExit('Checkpoint belongs to a different input. Use another output directory.')
    db.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('input_sha256', digest))
    db.execute('CREATE TABLE IF NOT EXISTS results (row_index INTEGER PRIMARY KEY, status TEXT, bizno TEXT, category TEXT, keyword TEXT, detail TEXT, elapsed_s REAL)')
    for index, row in enumerate(rows):
        if target_host(row['홈페이지1']) is None:
            db.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?)', (index, 'input_invalid', None, None, None, 'missing or malformed public URL', 0))
    db.commit()
    done = {r[0] for r in db.execute('SELECT row_index FROM results WHERE status IN ("ok", "input_invalid")')}
    if len(done) == len(rows):
        export(db, rows, args.output_dir)
        print('All %d rows already accounted for; no completed predictions were rerun.' % len(rows), flush=True)
        db.close()
        return 0
    pending = iter(index for index in range(len(rows)) if index not in done)
    context = mp.get_context('spawn')
    slots = [start_worker(context) for _ in range(args.workers)]
    completed = len(done)
    exhausted = False
    try:
        while slots:
            for slot in list(slots):
                now = time.monotonic()
                if not slot['process'].is_alive() or now - slot['started'] > (args.timeout if slot['task'] is not None else 120):
                    if slot['task'] is not None:
                        index = slot['task']
                        record = (index, 'timeout' if slot['process'].is_alive() else 'worker_error', None, None, None, 'worker restarted', now - slot['started'])
                        db.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?)', record)
                        db.commit()
                        completed += 1
                    elif not slot['ready']:
                        raise RuntimeError('Worker could not initialize the cached model.')
                    stop_worker(slot)
                    slots.remove(slot)
                    if not exhausted:
                        slots.append(start_worker(context))
                    continue
                if slot['pipe'].poll():
                    message = slot['pipe'].recv()
                    if message[0] == 'ready':
                        slot['ready'] = True
                    else:
                        record = message[1]
                        db.execute('INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?)', record)
                        db.commit()
                        completed += 1
                        print('progress %d/%d row=%d status=%s cate=%s' % (completed, len(rows), record[0], record[1], record[3]), flush=True)
                        if completed % 10 == 0:
                            export(db, rows, args.output_dir)
                        slot['task'] = None
                if slot['ready'] and slot['task'] is None:
                    try:
                        index = next(pending)
                    except StopIteration:
                        exhausted = True
                        slot['pipe'].send(None)
                        stop_worker(slot)
                        slots.remove(slot)
                    else:
                        row = rows[index]
                        slot['task'] = index
                        slot['started'] = time.monotonic()
                        slot['pipe'].send((index, row['사업체명'], row['홈페이지1'].strip()))
            time.sleep(0.1)
    finally:
        for slot in slots:
            stop_worker(slot)
        export(db, rows, args.output_dir)
        counts = dict(db.execute('SELECT status, COUNT(*) FROM results GROUP BY status'))
        print('Outcome counts:', json.dumps(counts), flush=True)
        db.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
