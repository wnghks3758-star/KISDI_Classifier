#!/usr/bin/env bash
set -euo pipefail
cd /workspace/KISDI_Classifier
test -f requirements.txt
test -f /workspace/.kisdi/requirements-cloud.lock
test -f /workspace/.kisdi/env.sh
mkdir -p /workspace/.kisdi/{bin,cache,python,browser,tessdata,results,config,selenium,huggingface}
source /workspace/.kisdi/env.sh

# Use Linux Python; never reuse the Windows virtualenv in the supplied ZIP.
uv python install 3.8.20
if [ ! -x /workspace/.kisdi/venv/bin/python ]; then
  uv venv --python /workspace/.kisdi/python/cpython-3.8-linux-x86_64-gnu/bin/python3.8 /workspace/.kisdi/venv
fi
uv pip install --python /workspace/.kisdi/venv/bin/python 'torch==2.4.0+cpu' --index-url https://download.pytorch.org/whl/cpu
uv pip install --python /workspace/.kisdi/venv/bin/python -r /workspace/.kisdi/requirements-cloud.lock
uv pip check --python /workspace/.kisdi/venv/bin/python

# Retained Debian packages were obtained using signed Debian repository metadata.
# Fetch the same pinned packages only if the retained snapshot lacks them.
mkdir -p /workspace/.kisdi/debs /workspace/.kisdi/apt/{lists/partial,cache/archives/partial,configparts}
if [ ! -f /workspace/.kisdi/debs/chromium_155.0.8059.39-1~deb13u1_amd64.deb ] ||
   [ ! -f /workspace/.kisdi/debs/chromium-common_155.0.8059.39-1~deb13u1_amd64.deb ] ||
   [ ! -f /workspace/.kisdi/debs/chromium-driver_155.0.8059.39-1~deb13u1_amd64.deb ]; then
  cat > /workspace/.kisdi/apt/sources.list <<'SOURCES'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian-security trixie-security main
SOURCES
  apt_options=(
    -o Dir::Etc::sourcelist=/workspace/.kisdi/apt/sources.list
    -o Dir::Etc::sourceparts=-
    -o Dir::Etc::parts=/workspace/.kisdi/apt/configparts
    -o Dir::State::lists=/workspace/.kisdi/apt/lists
    -o Dir::Cache=/workspace/.kisdi/apt/cache
    -o APT::Sandbox::User=agent
    -o APT::Update::Error-Mode=any
  )
  apt-get "${apt_options[@]}" update
  (
    cd /workspace/.kisdi/debs
    apt-get "${apt_options[@]}" download chromium=155.0.8059.39-1~deb13u1 chromium-common=155.0.8059.39-1~deb13u1 chromium-driver=155.0.8059.39-1~deb13u1
  )
fi
sha256sum --check <<'CHECKSUMS'
e60867eb02f3b9308d44f3a2b674c582340e3785035aa73a3800fcd25da6ae55  /workspace/.kisdi/debs/chromium_155.0.8059.39-1~deb13u1_amd64.deb
09682f63de57e45c419eea062a20177693a4904bb94403b53843d11489ecf259  /workspace/.kisdi/debs/chromium-common_155.0.8059.39-1~deb13u1_amd64.deb
b5f67f7e211b2d96095785d2ddeb785aedcb4b28e81436e8e424c36f2f0211f9  /workspace/.kisdi/debs/chromium-driver_155.0.8059.39-1~deb13u1_amd64.deb
CHECKSUMS
if [ ! -x /workspace/.kisdi/browser/usr/bin/chromedriver ]; then
  for package in /workspace/.kisdi/debs/chromium*.deb; do
    dpkg-deb --extract "$package" /workspace/.kisdi/browser
  done
fi
test -x /workspace/.kisdi/bin/chromium
test -x /workspace/.kisdi/bin/chromedriver
chromium --version
chromedriver --version

if [ ! -f /workspace/.kisdi/tessdata/kor.traineddata ]; then
  curl --fail --location --silent --show-error --output /workspace/.kisdi/tessdata/kor.traineddata \
    https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/kor.traineddata
fi
sha256sum --check <<'CHECKSUMS'
6b85e11d9bbf07863b97b3523b1b112844c43e713df8b66418a081fd1060b3b2  /workspace/.kisdi/tessdata/kor.traineddata
CHECKSUMS
test -x /usr/bin/tesseract
tesseract --list-langs
for category in 201 202 203; do
  test -f "필요파일/classifier-kor-base_${category}.pth"
done

# The user explicitly approved trusting this environment-provided public proxy CA.
# Preserve existing certificates and use a distinct name for each CA fingerprint.
test -f /usr/local/share/ca-certificates/environment-proxy-ca.crt
kisdi_ca_fingerprint=$(openssl x509 -in /usr/local/share/ca-certificates/environment-proxy-ca.crt -noout -fingerprint -sha256)
kisdi_ca_name="KISDI-${kisdi_ca_fingerprint#*=}"
kisdi_nss_db="sql:${HOME}/.pki/nssdb"
if ! certutil -d "$kisdi_nss_db" -L -n "$kisdi_ca_name" >/dev/null 2>&1; then
  certutil -d "$kisdi_nss_db" -A -t 'C,,' -n "$kisdi_ca_name" -i /usr/local/share/ca-certificates/environment-proxy-ca.crt
fi
# Preload the public base model and tokenizer so normal startup can run offline.
HF_HUB_OFFLINE=0 TRANSFORMERS_OFFLINE=0 /workspace/.kisdi/venv/bin/python - <<'PY'
from transformers import AutoModel, AutoTokenizer
model = AutoModel.from_pretrained('klue/roberta-base')
tokenizer = AutoTokenizer.from_pretrained('klue/roberta-base')
print('Base model and tokenizer cache prepared')
PY
