## Figma 디자인을 HTML/CSS로 변환하는 Python 도구

### 기능

- Figma JSON_REST_V1 형식 API 통합
- 재귀 기반 고급 노드 처리
- GROUP 노드 자동 평면화
- 타입 기반 HTML 생성
- 고유 CSS 클래스명 생성 및 스타일 수집
- 성능 측정 기능 포함
- 지원되지 않는 기능에 대한 경고 제공

### React 컴포넌트 생성 기능

- 단일 노드를 React TSX 컴포넌트로 변환
- 선택된 노드의 모든 컴포넌트를 일괄 변환
- COMPONENT/INSTANCE 타입 필터링 옵션
- 최소 크기 조건 (10x10px 이상)을 만족하는 노드만 처리
- 중복 이름 제거 및 크기 기준 정렬

### React 페이지 생성 기능

- HTML/CSS를 React TSX 페이지로 변환
- 기존 컴포넌트 디렉토리 활용 가능
- 컴포넌트 없이 HTML/CSS만으로도 페이지 생성 가능
- HTML/CSS와 TSX 페이지를 별도 디렉토리에 저장 가능

### 설치

```bash
cd figma2html
pip install -r requirements.txt
```

### 설정

1. Figma API 토큰 발급: https://www.figma.com/developers/api#access-tokens
2. 환경 변수 설정

```bash
export FIGMA_API_TOKEN="your_token_here"
```

또는 .env 파일 생성

```bash
FIGMA_API_TOKEN=your_token_here
OPENROUTER_API_KEY=your_token_here
AOAI_ENDPOINT=azure_endpoint
AOAI_API_KEY=your_azure_api_key
AOAI_DEPLOY_GPT4O=gpt-4o
IS_ROUTER=True/False
```

(figma2html만 이용할거라면 FIGMA_API_TOKEN, 모든 기능을 이용할거라면 .env에 존재)

### 사용법

- 기본 변환

```bash
python -m src.main convert "https://www.figma.com/design/your-file-key/your-design"
```

- 출력 디렉토리 지정

```bash
python -m src.main convert "figma-url" --output my-output
```

- 토큰 직접 입력

```bash
python -m src.main convert "figma-url" --token your_token
```

- 다중 React 컴포넌트 변환

```bash
python -m src.main convert-react-selection "figma-url" --filter-components
```

- React 페이지 생성 (HTML/CSS + TSX)

```bash
python -m src.main create-page "figma-url"
```

- React 페이지 생성 (커스텀 컴포넌트 디렉토리 지정)

```bash
python -m src.main create-page "figma-url" --components "./my-components"
```

- React 페이지 생성 (커스텀 출력 디렉토리, 커스텀 컴포넌트 디렉토리 지정)

```bash
python -m src.main create-page "figma-url" --pages "./tsx-pages" --components "./my-components"
```

- 성능 측정

```bash
python -m src.main benchmark "figma-url"
```

- URL 유효성 확인

```bash
python -m src.main info "figma-url"
```

- 설정 도움말

```bash
python -m src.main setup
```

### 아키텍처

1. FigmaApiClient

- REST API 연동, JSON_REST_V1 형식 지원, 비동기 요청

2. JsonNodeConverter

- 재귀 처리, 그룹 및 회전 변환, 고유 이름 생성, 성능 통계 수집

3. HtmlGenerator

- 노드 타입에 따른 HTML 변환, CSS 클래스 처리, 자동 레이아웃 지원

4. CSSStyleBuilder

- 스타일 빌드, 색상/그라디언트/간격/폰트 등 CSS 생성

5. Utils

- 공통 함수, 이름 정리, 메타데이터 처리

6. ReactGenerator

- 단일 React TSX 컴포넌트 생성
- LLM 기반 코드 생성 (OpenRouter/Azure OpenAI)

7. PageGenerator

- HTML/CSS를 React TSX 페이지로 변환
- 기존 컴포넌트 활용 또는 순수 HTML/CSS 기반 생성
- LLM 기반 레이아웃 생성

### 처리 흐름

**기본 변환:**

1. API 데이터 가져오기
2. 노드 재귀 처리
3. HTML/CSS 생성
4. 파일 저장

**React 컴포넌트 생성:**

1. Figma 노드 데이터 추출
2. LLM 기반 React TSX 코드 생성
3. 컴포넌트 파일 저장

**React 페이지 생성:**

1. HTML/CSS 생성 (기본 변환)
2. 기존 컴포넌트 분석 (선택사항)
3. LLM 기반 React TSX 페이지 생성
4. HTML/CSS와 TSX 페이지 각각 저장

### 출력 구조

**기본 변환:**

```
output/
├── design_name/
│   ├── design_name.html
│   └── design_name.css
└── responses/
    ├── response_1.json
    └── response_2.json
```

**React 컴포넌트:**

```
frontend/src/test-components/
├── ComponentName.tsx
├── AnotherComponent.tsx
└── ...
```

**React 페이지:**

```
output/                    # HTML/CSS 파일
├── design_name/
│   ├── design_name.html
│   └── design_name.css

frontend/src/pages/        # TSX 페이지 파일
└── DesignNamePage.tsx
```

### 성능 측정

- API 응답 시간
- 노드 처리 시간
- HTML 생성 시간
- 노드 통계 포함

### 에러처리

- 지원되지 않는 노드
- 임베드되지 않은 벡터
- 불완전하게 변환될 수 있는 복잡한 구조

### 지원되는 Figma 기능

노드 타입

- FRAME, COMPONENT, INSTANCE
- TEXT (스타일 포함)
- RECTANGLE, ELLIPSE
- GROUP, SECTION, LINE
- VECTOR (플레이스홀더 처리)

스타일링

- 자동 레이아웃 (flex)
- 절대 위치
- 색상, 그라디언트
- 타이포그래피
- 테두리, 반경
- 그림자, 효과
- 불투명도

레이아웃

- 반응형 컨테이너
- 플렉스 수평/수직
- 간격, 패딩, 정렬

### 개발 및 테스트

- JSON 변환 테스트

```bash
python -m src.json_node_converter
```

- HTML 생성 테스트

```bash
python -m src.html_generator
```

- 스타일 빌드 테스트

```bash
python -m src.style_builder
```

### 제한사항

- 벡터는 플레이스홀더 div로 변환됨
- 이미지 채우기는 임시 URL 사용
- 일부 고급 기능은 미지원
- 큰 파일은 API 속도 제한 있음
