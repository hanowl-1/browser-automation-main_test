# 🚀 Browser Automation 프로젝트 설치 가이드

## 필수 요구사항

- Python 3.11 이상
- macOS, Linux, 또는 Windows
- OpenAI API 키

## 설치 방법

### 1. 압축 파일 해제

```bash
unzip browser-automation.zip
cd browser-automation
```

### 2. Python 환경 설정

#### 방법 A: uv 사용 (권장)

```bash
# uv 설치 (없는 경우)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 가상 환경 생성
uv venv --python 3.11

# 가상 환경 활성화
source .venv/bin/activate  # Mac/Linux
# 또는
.venv\Scripts\activate     # Windows

# 패키지 설치
uv pip install browser-use python-dotenv

# Playwright 브라우저 설치
uv run playwright install
```

#### 방법 B: pip 사용

```bash
# 가상 환경 생성
python3 -m venv .venv

# 가상 환경 활성화
source .venv/bin/activate  # Mac/Linux
# 또는
.venv\Scripts\activate     # Windows

# 패키지 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install
```

### 3. 실행

#### 간단한 실행 방법:

```bash
# run.sh 스크립트 사용 (Mac/Linux)
chmod +x run.sh
./run.sh
```

#### 직접 실행:

```bash
# 가상 환경 활성화 후
python 1_login.py
```

## 문제 해결

### "command not found: python" 오류

- `python3` 명령어 사용

### ModuleNotFoundError

- 가상 환경이 활성화되었는지 확인
- 패키지가 설치되었는지 확인: `pip list`

### Browser 실행 오류

- Playwright 브라우저 재설치: `playwright install`

## 파일 설명

- `tiktok1_login.py`: TikTok Shop 로그인 자동화
- `main.py`: 기본 Browser Use 예제
- `requirements.txt`: Python 패키지 목록
- `run.sh`: 실행 헬퍼 스크립트
- `.env`: 환경 변수
- `CLAUDE.md`: 프로젝트 문서 (Claude Code용)
- `README.md`: 프로젝트 소개

## 주의사항

⚠️ **절대 `.env` 파일을 공유하지 마세요!** API 키와 비밀번호가 포함되어 있습니다.

## 지원

문제가 있으면 README.md 파일을 참조하거나 프로젝트 문서를 확인하세요.
