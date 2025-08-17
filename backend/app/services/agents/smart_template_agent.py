"""
Smart Template Generation Agent
텍스트 설명과 첨부파일을 기반으로 React 프로젝트를 지능적으로 생성하는 에이전트
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.core.config import settings
from .image_utils import process_attachment_for_claude
from .utils import call_anthropic_api

logger = logging.getLogger("app.smart_template_agent")


class SmartTemplateAgent:
    """스마트 템플릿 생성 에이전트"""
    
    def __init__(self):
        self.base_template_path = Path(__file__).parent.parent.parent / "templates" / "react_boilerplate"
    
    async def generate_project(
        self,
        description: str,
        attachments: List[Dict[str, Any]] = None,
        style_preferences: str = "",
        app_name: str = "smart-react-app",
        title: str = "Smart React App"
    ) -> Dict[str, Any]:
        """
        텍스트 설명과 첨부파일을 기반으로 React 프로젝트를 생성합니다.
        
        Args:
            description: 프로젝트에 대한 텍스트 설명
            attachments: 첨부파일 리스트 (이미지, MD, PDF 등)
            style_preferences: 스타일 선호도
            app_name: 앱 이름
            title: 프로젝트 제목
            
        Returns:
            Dict: 생성 결과
        """
        try:
            logger.info(f"스마트 프로젝트 생성 시작: {app_name}")
            
            # 1. 첨부파일 처리
            processed_attachments = []
            if attachments:
                for attachment in attachments:
                    processed = await process_attachment_for_claude(attachment)
                    if processed:
                        processed_attachments.append(processed)
            
            # 2. LLM에게 프로젝트 생성 요청
            project_analysis = await self._analyze_requirements(
                description, processed_attachments, style_preferences
            )
            
            if not project_analysis.get("success"):
                return {"success": False, "message": "요구사항 분석 실패"}
            
            # 3. 컴포넌트와 페이지 생성
            generated_files = await self._generate_components_and_pages(
                project_analysis["analysis"], app_name, title
            )
            
            # 4. 필요한 의존성 분석
            dependencies = self._analyze_dependencies(project_analysis["analysis"])
            
            return {
                "success": True,
                "summary": project_analysis["analysis"].get("summary", "프로젝트가 생성되었습니다."),
                "generated_files": generated_files,
                "dependencies": dependencies,
                "component_list": [file["name"] for file in generated_files if file["type"] == "component"]
            }
            
        except Exception as e:
            logger.error(f"스마트 프로젝트 생성 중 오류: {e}")
            return {"success": False, "message": str(e)}
    
    async def _analyze_requirements(
        self, 
        description: str, 
        attachments: List[Dict[str, Any]], 
        style_preferences: str
    ) -> Dict[str, Any]:
        """요구사항을 분석하고 프로젝트 구조를 계획합니다."""
        
        messages = []
        
        # 시스템 메시지
        system_message = """
당신은 React 프로젝트 설계 전문가입니다. 사용자의 설명과 첨부파일을 분석하여 다음을 제공해주세요:

1. 프로젝트 개요 및 목적
2. 필요한 주요 페이지들 (경로와 함께)
3. 필요한 주요 컴포넌트들
4. 권장 UI 라이브러리 및 스타일링 방식
5. 필요한 추가 npm 패키지들
6. 전체적인 디자인 컨셉 및 컬러 스키마

응답은 반드시 다음 JSON 형식으로 제공해주세요:
{
  "summary": "프로젝트 요약",
  "pages": [
    {"name": "HomePage", "path": "/", "description": "메인 페이지"},
    {"name": "AboutPage", "path": "/about", "description": "소개 페이지"}
  ],
  "components": [
    {"name": "Header", "type": "layout", "description": "상단 헤더"},
    {"name": "Button", "type": "ui", "description": "재사용 가능한 버튼"}
  ],
  "design_system": {
    "theme": "modern/minimalist/colorful/etc",
    "primary_color": "#color",
    "secondary_color": "#color",
    "ui_library": "shadcn-ui/material-ui/tailwind/etc"
  },
  "npm_packages": ["package1", "package2"]
}
"""
        
        # 사용자 메시지 구성
        user_content = []
        user_content.append({
            "type": "text",
            "text": f"""
프로젝트 설명: {description}

스타일 선호도: {style_preferences or '특별한 선호도 없음'}

첨부파일들을 참고하여 사용자가 원하는 프로젝트를 분석해주세요.
"""
        })
        
        # 첨부파일 추가
        if attachments:
            user_content.extend(attachments)
        
        messages.append({"role": "user", "content": user_content})
        
        try:
            response = await call_anthropic_api(
                messages=messages,
                system=system_message,
                model="claude-3-sonnet-20241022",
                max_tokens=4000
            )
            
            # JSON 파싱
            response_text = response.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3]
            elif response_text.startswith("```"):
                response_text = response_text[3:-3]
            
            analysis = json.loads(response_text)
            
            return {"success": True, "analysis": analysis}
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {e}, 응답: {response}")
            return {"success": False, "message": f"응답 파싱 실패: {e}"}
        except Exception as e:
            logger.error(f"요구사항 분석 오류: {e}")
            return {"success": False, "message": str(e)}
    
    async def _generate_components_and_pages(
        self, 
        analysis: Dict[str, Any], 
        app_name: str, 
        title: str
    ) -> List[Dict[str, Any]]:
        """분석 결과를 바탕으로 실제 컴포넌트와 페이지 파일들을 생성합니다."""
        
        generated_files = []
        
        try:
            # 1. 페이지 생성
            for page in analysis.get("pages", []):
                page_content = await self._generate_page_component(page, analysis)
                if page_content:
                    generated_files.append({
                        "type": "page",
                        "name": page["name"],
                        "path": f"client/pages/{page['name']}.tsx",
                        "content": page_content
                    })
            
            # 2. 컴포넌트 생성
            for component in analysis.get("components", []):
                component_content = await self._generate_ui_component(component, analysis)
                if component_content:
                    component_path = f"client/components/{'ui/' if component['type'] == 'ui' else ''}{component['name']}.tsx"
                    generated_files.append({
                        "type": "component",
                        "name": component["name"],
                        "path": component_path,
                        "content": component_content
                    })
            
            # 3. App.tsx 업데이트
            app_content = await self._generate_app_component(analysis)
            if app_content:
                generated_files.append({
                    "type": "app",
                    "name": "App",
                    "path": "client/App.tsx",
                    "content": app_content
                })
            
            return generated_files
            
        except Exception as e:
            logger.error(f"컴포넌트 생성 오류: {e}")
            return []
    
    async def _generate_page_component(self, page: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """개별 페이지 컴포넌트를 생성합니다."""
        
        system_message = f"""
당신은 React/TypeScript 전문 개발자입니다. 다음 페이지를 위한 React 컴포넌트를 생성해주세요:

페이지 정보:
- 이름: {page['name']}
- 경로: {page['path']}
- 설명: {page['description']}

디자인 시스템:
{json.dumps(analysis.get('design_system', {}), indent=2)}

요구사항:
1. TypeScript를 사용해주세요
2. 함수형 컴포넌트로 작성해주세요
3. Tailwind CSS를 사용해주세요
4. 반응형 디자인을 고려해주세요
5. 접근성을 고려해주세요
6. 컴포넌트 파일 전체 내용만 제공해주세요 (설명 없이)

응답은 완전한 TypeScript React 컴포넌트 파일 내용만 제공해주세요.
"""
        
        messages = [
            {
                "role": "user",
                "content": f"'{page['name']}' 페이지 컴포넌트를 생성해주세요."
            }
        ]
        
        try:
            response = await call_anthropic_api(
                messages=messages,
                system=system_message,
                model="claude-3-sonnet-20241022",
                max_tokens=3000
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"페이지 생성 오류 ({page['name']}): {e}")
            return ""
    
    async def _generate_ui_component(self, component: Dict[str, Any], analysis: Dict[str, Any]) -> str:
        """개별 UI 컴포넌트를 생성합니다."""
        
        system_message = f"""
당신은 React/TypeScript 전문 개발자입니다. 다음 컴포넌트를 위한 재사용 가능한 React 컴포넌트를 생성해주세요:

컴포넌트 정보:
- 이름: {component['name']}
- 타입: {component['type']}
- 설명: {component['description']}

디자인 시스템:
{json.dumps(analysis.get('design_system', {}), indent=2)}

요구사항:
1. TypeScript를 사용해주세요
2. 함수형 컴포넌트로 작성해주세요
3. Props 인터페이스를 정의해주세요
4. Tailwind CSS를 사용해주세요
5. 재사용 가능하도록 설계해주세요
6. 컴포넌트 파일 전체 내용만 제공해주세요 (설명 없이)

응답은 완전한 TypeScript React 컴포넌트 파일 내용만 제공해주세요.
"""
        
        messages = [
            {
                "role": "user", 
                "content": f"'{component['name']}' 컴포넌트를 생성해주세요."
            }
        ]
        
        try:
            response = await call_anthropic_api(
                messages=messages,
                system=system_message,
                model="claude-3-sonnet-20241022",
                max_tokens=2000
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"컴포넌트 생성 오류 ({component['name']}): {e}")
            return ""
    
    async def _generate_app_component(self, analysis: Dict[str, Any]) -> str:
        """메인 App 컴포넌트를 생성합니다."""
        
        pages = analysis.get("pages", [])
        
        system_message = f"""
당신은 React/TypeScript 전문 개발자입니다. React Router를 사용하는 메인 App 컴포넌트를 생성해주세요.

페이지 정보:
{json.dumps(pages, indent=2)}

요구사항:
1. TypeScript를 사용해주세요
2. React Router (react-router-dom)를 사용해주세요
3. 모든 페이지에 대한 라우팅을 설정해주세요
4. 404 페이지 처리도 포함해주세요
5. 컴포넌트 파일 전체 내용만 제공해주세요 (설명 없이)

응답은 완전한 TypeScript React App 컴포넌트 파일 내용만 제공해주세요.
"""
        
        messages = [
            {
                "role": "user",
                "content": "메인 App 컴포넌트를 생성해주세요."
            }
        ]
        
        try:
            response = await call_anthropic_api(
                messages=messages,
                system=system_message,
                model="claude-3-sonnet-20241022",
                max_tokens=2000
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"App 컴포넌트 생성 오류: {e}")
            return ""
    
    def _analyze_dependencies(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """분석 결과를 바탕으로 필요한 npm 의존성을 결정합니다."""
        
        dependencies = {}
        
        # 기본 의존성
        npm_packages = analysis.get("npm_packages", [])
        
        for package in npm_packages:
            if package == "react-router-dom":
                dependencies["react-router-dom"] = "^6.8.0"
            elif package == "axios":
                dependencies["axios"] = "^1.3.0"
            elif package == "react-query" or package == "@tanstack/react-query":
                dependencies["@tanstack/react-query"] = "^4.24.0"
            elif package == "framer-motion":
                dependencies["framer-motion"] = "^10.0.0"
            elif package == "react-hook-form":
                dependencies["react-hook-form"] = "^7.43.0"
            elif package == "zod":
                dependencies["zod"] = "^3.20.0"
            # 더 많은 패키지 매핑 추가 가능
        
        return dependencies
    
    async def apply_generated_files(self, project_path: Path, generated_files: List[Dict[str, Any]]):
        """생성된 파일들을 실제 프로젝트 디렉토리에 적용합니다."""
        
        try:
            for file_info in generated_files:
                file_path = project_path / file_info["path"]
                
                # 디렉토리가 없으면 생성
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                # 파일 생성
                file_path.write_text(file_info["content"], encoding="utf-8")
                
                logger.info(f"파일 생성 완료: {file_path}")
                
        except Exception as e:
            logger.error(f"파일 적용 오류: {e}")
            raise