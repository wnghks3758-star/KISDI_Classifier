# KISDI_Classifier

웹사이트의 키워드, 이용약관과 BERT 모델을 이용하는 201·202·203 분류 코드입니다. 사용자 제공 ZIP의 원본 코드를 복원했고, 클라우드 환경에서 사용한 실행 도구와 작업 기록을 함께 보관합니다.

## 파일 구성

| 경로 | 내용 |
| --- | --- |
| `processing_model_201.py`, `processing_model_202.py`, `processing_model_203.py` | 원본 업태별 분류 코드 |
| `processing_model_all.py` | 세 분류를 실행하는 원본 대화형 CLI |
| `function/` | 웹 수집, 키워드 검색, 약관 BERT 분류, 앱 링크 탐지 |
| `필요파일/*.pickle` | 원본 키워드·플랫폼 사전 |
| `requirements.txt`, `read_me.txt` | 원본 의존성 목록과 실행 메모 |
| `scripts/predict_202_full.py` | 전체 행 처리, 중간 저장과 재개를 지원하는 202 실행기 |
| `scripts/validate.py`, `scripts/validate_batch.py` | 클라우드에서 사용한 기능·모델·CLI 검증 도구 |
| `cloud/` | 기존 클라우드 환경의 설정과 의존성 고정 목록 |
| [docs/PROGRESS.md](docs/PROGRESS.md) | 완료한 작업, 검증 범위, 현재 미완료 사항 |

## 실행 환경

검증한 구성은 Python 3.8.20, CPU PyTorch 2.4.0+cpu, Transformers 4.44.2, Chromium/ChromeDriver 155 및 한국어 Tesseract OCR입니다. 세부 패키지 버전은 `cloud/requirements-cloud.lock`에 있습니다.

현재 실행 도구는 기존 클라우드 스냅샷의 `/workspace/KISDI_Classifier` 및 `/workspace/.kisdi` 경로를 사용합니다. `cloud/install.sh`는 그 스냅샷을 위한 설치 스크립트이며, 새 컴퓨터에서 저장소만 복제해 모든 준비를 마치는 설치 프로그램은 아닙니다. 브라우저, OCR, 기본 모델 캐시 및 아래 체크포인트가 별도로 필요합니다.

### 모델 파일 준비

사용자 제공 원본 `KISDI-classifier.zip`에서 다음 파일을 `필요파일/`에 복원합니다. 체크포인트는 각각 약 443MB이므로 Git 저장소에서 제외했습니다.

```text
필요파일/classifier-kor-base_201.pth
필요파일/classifier-kor-base_202.pth
필요파일/classifier-kor-base_203.pth
```

원본 파일의 SHA-256은 [docs/assets.sha256](docs/assets.sha256)에 기록돼 있습니다. 기본 모델·토크나이저는 Hugging Face의 `klue/roberta-base`이며, 기존 환경에는 오프라인 실행용 캐시가 있습니다. 별도 전체 행 실행기는 BERT의 평가 모드와 기울기 계산 비활성화를 적용합니다.

### 기존 클라우드 환경에서 실행

기존 `/workspace/.kisdi` 환경과 의존성이 준비된 상태에서 실행합니다.

```bash
cd /workspace/KISDI_Classifier
source /workspace/.kisdi/env.sh
python processing_model_all.py
```

CLI에 입력 CSV 경로와 201·202·203의 출력 Excel 경로를 차례로 입력합니다. **원본 업태별 프로세서는 첫 20행만 처리합니다.** 전체 행은 아래 별도 실행기를 사용합니다.

입력 CSV는 CP949 인코딩이며 `사업체명`, `홈페이지1` 열이 필요합니다. 사업자 원본 CSV와 수집·예측 결과는 저장소에 포함하지 않았습니다.

### 202 전체 행 실행기

```bash
python scripts/predict_202_full.py \
  --input /path/to/input.csv \
  --output-dir /workspace/.kisdi/results/202-new-sample \
  --allowlist /path/to/allowed-hosts.json \
  --workers 1 \
  --limit 100
```

`allowed-hosts.json`은 허용된 호스트 문자열의 JSON 배열입니다. 예: `["example.com", "www.example.com"]`. 실제 환경의 네트워크 정책과 일치하게 지정해야 하며, 이 파일을 수정해도 환경의 접근 권한이 늘어나지는 않습니다. 첫 실행은 모델을 하나만 적재하도록 `--workers 1`을 권장합니다. 이 실행기는 입력 전체를 메모리에 읽으므로 대형 원본을 스트리밍으로 정리한 작은 입력을 먼저 준비해야 합니다.

결과는 SQLite 체크포인트와 CSV·Excel로 저장됩니다. 같은 입력·옵션·출력 폴더로 재실행하면 성공한 행을 건너뛰고 실패한 행을 재시도합니다. 입력이나 `--limit`이 바뀌면 새 출력 폴더를 사용합니다. 접속 오류와 수집 실패는 별도 상태로 기록하며 `status=ok`인 행만 성공한 처리로 집계합니다. 사이트 접속 실패는 업체의 폐업을 뜻하지 않습니다.

## 검증과 현재 상태

2026-10-14에 원본 코드·모델 등 20개 파일을 복원하고 기존 SHA-256과 대조했습니다. 캐시를 사용한 202 BERT 예측의 실행과 반복 결과 일치를 확인했습니다. 이는 최신 업체 목록에 대한 정확도 평가 결과는 아닙니다.

최신 서울 통신판매사업자 CSV는 채팅에 첨부됐으나, 실행 도구의 32MiB 전송 제한으로 아직 읽거나 분류하지 못했습니다. 다음 작업은 필요한 열·홈페이지가 있는 행을 추리고 100~200건에서 모델 예측과 독립적인 웹 근거 검토 라벨을 만드는 것입니다.
