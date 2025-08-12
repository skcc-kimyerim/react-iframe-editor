# React Iframe Editor

React 기반 코드 에디터와 라이브 프리뷰 기능을 제공하는 웹 애플리케이션입니다.

## 프로젝트 구조

```
react-iframe-editor/
├── backend/          # FastAPI 백엔드 서버
├── frontend/         # React 프론트엔드 애플리케이션
└── README.md
```

## 실행 방법

### 1. 환경 변수 설정

#### 백엔드 환경 변수

`backend/` 디렉토리에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```bash
# 백엔드 서버 포트 설정
PORT=3001
REACT_DEV_PORT=3002

# Figma API (선택사항)
FIGMA_API_TOKEN=your_figma_token_here

# LLM 서비스 설정 (선택사항)
# OpenRouter 사용 시
OPENROUTER_API_KEY=your_openrouter_api_key
IS_ROUTER=True

# 또는 Azure OpenAI 사용 시
AOAI_ENDPOINT=your_azure_endpoint
AOAI_API_KEY=your_azure_api_key
AOAI_DEPLOY_GPT4O=gpt-4o
IS_ROUTER=False

# CORS 설정 (기본값: 모든 도메인 허용)
CORS_ALLOW_ORIGINS=["*"]
```

#### 프론트엔드 환경 변수

`frontend/` 디렉토리에 `.env` 파일을 생성하고 다음 내용을 추가하세요:

```bash
# 백엔드 API 서버 주소
VITE_REACT_APP_API_URL=http://localhost:3001
```

### 2. 백엔드 실행

```bash
# 백엔드 디렉토리로 이동
cd backend

# Python 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 서버 실행
python main.py
```

백엔드 서버가 `http://localhost:3001`에서 실행됩니다.

### 3. 프론트엔드 실행

새 터미널에서:

```bash
# 프론트엔드 디렉토리로 이동
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm start
```

프론트엔드 애플리케이션이 `http://localhost:3000`에서 실행됩니다.

## API 엔드포인트

백엔드 API는 다음 주소에서 확인할 수 있습니다:

- API 문서: `http://localhost:3001/docs`
- API 기본 경로: `http://localhost:3001/api/`

## 주요 기능

- **코드 에디터**: Monaco Editor를 사용한 코드 편집
- **라이브 프리뷰**: 실시간 코드 미리보기
- **파일 트리**: 프로젝트 파일 구조 탐색
- **Figma 통합**: Figma 디자인을 HTML/React로 변환 (선택사항)
- **AI 채팅**: LLM을 활용한 코드 지원 (선택사항)

## 문제 해결

### 포트 충돌 시

`backend/.env` 파일에서 `PORT`와 `REACT_DEV_PORT` 값을 변경하고, `frontend/.env` 파일의 `REACT_APP_API_URL`도 함께 업데이트하세요.

### API 연결 오류 시

- 백엔드 서버가 실행 중인지 확인하세요
- `frontend/.env` 파일의 `REACT_APP_API_URL`이 올바른 백엔드 주소인지 확인하세요
- 브라우저 개발자 도구의 Network 탭에서 API 요청 상태를 확인하세요

### 의존성 설치 오류 시

- Python: `pip install --upgrade pip` 후 재시도
- Node.js: `npm cache clean --force` 후 재시도

### CORS 오류 시

`backend/.env` 파일에서 `CORS_ALLOW_ORIGINS` 설정을 확인하세요.

### 환경 변수가 인식되지 않을 때

- React 앱은 `REACT_APP_` 접두어가 있는 환경 변수만 인식합니다
- 환경 변수 변경 후 개발 서버를 재시작하세요
- `.env` 파일이 올바른 디렉토리에 있는지 확인하세요 (`backend/.env`, `frontend/.env`)
