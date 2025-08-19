# React Iframe Editor

React 기반 코드 에디터와 라이브 프리뷰 기능을 제공하는 웹 애플리케이션입니다. Figma 디자인을 React 컴포넌트로 변환하고, AI 채팅을 통한 스마트 코드 생성을 지원합니다.

## 프로젝트 구조

```
react-iframe-editor/
├── backend/          # FastAPI 백엔드 서버
│   ├── app/          # 메인 애플리케이션
│   │   ├── routers/  # API 라우터 (chat, files, projects, uploads 등)
│   │   └── services/ # 비즈니스 로직 (AI 에이전트, 파일 관리 등)
│   ├── projects/     # 사용자 프로젝트 저장소
│   └── templates/    # 프로젝트 템플릿 (react_boilerplate)
├── frontend/         # React + Vite 프론트엔드 애플리케이션
├── figma2react/      # Figma to React 변환 서비스
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

# LLM 서비스 설정 (필수 - 하나만 선택)
# Anthropic Claude 사용 시 (권장)
ANTHROPIC_API_KEY=your_anthropic_api_key

# 또는 OpenRouter 사용 시
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
# 백엔드 API 서버 주소 (Vite에서는 VITE_ 접두어 필요)
VITE_REACT_APP_API_URL=http://localhost:3001
```

> **참고**: Vite는 `VITE_` 접두어가 있는 환경 변수만 클라이언트 측에서 접근할 수 있습니다.

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

# 개발 서버 실행 (Vite)
npm run dev
```

프론트엔드 애플리케이션이 `http://localhost:3000`에서 실행됩니다.

### 4. Figma2React 서비스 실행 (선택사항)

Figma 통합 기능을 사용하려면 figma2react 서비스도 실행해야 합니다:

```bash
# figma2react 디렉토리로 이동
cd figma2react

# UV 사용 (권장)
uv sync
uv run python app/main.py

# 또는 pip 사용
pip install -r requirements.txt
python app/main.py
```

Figma2React 서비스가 별도 포트에서 실행됩니다.

## API 엔드포인트

백엔드 API는 다음 주소에서 확인할 수 있습니다:

- API 문서: `http://localhost:3001/docs`
- API 기본 경로: `http://localhost:3001/api/`

## 주요 기능

### 🎨 프로젝트 관리

- **프로젝트 선택기**: Basic 및 Figma 프로젝트 타입 지원
- **스마트 프로젝트 생성**: AI를 활용한 프로젝트 초기 설정
- **프로젝트별 파일 관리**: 독립적인 프로젝트 환경 제공

### 💻 코드 에디터 & 개발 환경

- **Monaco Editor**: VSCode와 동일한 고급 코드 편집 기능
- **라이브 프리뷰**: 실시간 React 애플리케이션 미리보기
- **자동 개발 서버 관리**: 프로젝트별 React 개발 서버 자동 시작/중지
- **파일 트리**: 프로젝트 파일 구조 탐색 및 관리
- **라우트 선택**: React Router 경로 간 쉬운 탐색

### 🎨 Figma 통합

- **Figma URL 처리**: Figma 디자인 URL을 감지하여 자동 변환
- **Figma to React**: Figma 컴포넌트를 React 컴포넌트로 변환
- **디자인 시스템 통합**: Figma 디자인을 코드로 자동 생성

### 🤖 AI 채팅 & 코드 생성

- **LLM 통합**: Anthropic Claude, OpenRouter, Azure OpenAI 지원
- **스마트 코드 생성**: AI를 통한 컴포넌트 및 페이지 생성
- **파일 첨부**: 이미지 및 파일을 첨부하여 AI와 상호작용
- **컨텍스트 인식**: 현재 선택된 파일과 프로젝트 상태를 고려한 AI 응답

### 🔧 개발자 도구

- **WebSocket 로그**: 개발 서버 로그 실시간 확인
- **파일 업로드/다운로드**: 프로젝트 파일 관리 API
- **비동기 작업 처리**: 백그라운드 작업 상태 추적
- **에러 처리**: 상세한 에러 로그 및 사용자 피드백

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

- Vite 앱은 `VITE_` 접두어가 있는 환경 변수만 인식합니다
- 환경 변수 변경 후 개발 서버를 재시작하세요
- `.env` 파일이 올바른 디렉토리에 있는지 확인하세요 (`backend/.env`, `frontend/.env`)

### AI 채팅이 작동하지 않을 때

- `ANTHROPIC_API_KEY` 또는 선택한 LLM 서비스의 API 키가 올바르게 설정되었는지 확인하세요
- 백엔드 로그에서 API 요청 에러를 확인하세요
- API 키의 사용 한도와 유효성을 확인하세요

### Figma 통합 기능 문제

- `FIGMA_API_TOKEN`이 설정되어 있는지 확인하세요
- Figma URL이 올바른 형식인지 확인하세요 (공개 링크여야 함)
- figma2react 서비스가 실행 중인지 확인하세요

### 프로젝트가 생성되지 않을 때

- `backend/projects/` 디렉토리에 쓰기 권한이 있는지 확인하세요
- 디스크 용량이 충분한지 확인하세요
- 백엔드 로그에서 프로젝트 생성 관련 에러를 확인하세요

### 파일 업로드가 실패할 때

- 업로드하려는 파일 크기가 제한을 초과하지 않는지 확인하세요
- 지원되는 파일 형식인지 확인하세요 (이미지, 텍스트 파일 등)
- 네트워크 연결 상태를 확인하세요
