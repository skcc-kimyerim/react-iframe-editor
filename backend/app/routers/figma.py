from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import os
import tempfile
import shutil
from ..core.config import settings

# figma2html 모듈 임포트
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../../figma2html"))

from figma2html import FigmaToCode, parse_figma_url
from figma2html.src.react_generator import ReactComponentGenerator
from figma2html.src.page_generator import PageGenerator

# figma2html 모듈 경로 추가
figma_module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../figma2html"))
if figma_module_path not in sys.path:
    sys.path.insert(0, figma_module_path)

# figma2html 모듈 임포트
try:
    from src.main import FigmaToCode
    from src.figma_url_parser import parse_figma_url
    from src.react_generator import ReactComponentGenerator
    from src.page_generator import PageGenerator
    from src.utils import inject_metadata
except ImportError as e:
    logging.error(f"figma2html 모듈 import 실패: {e}")
    # Fallback으로 다른 방법 시도
    try:
        from figma2html.src.main import FigmaToCode
        from figma2html.src.figma_url_parser import parse_figma_url
        from figma2html.src.react_generator import ReactComponentGenerator
        from figma2html.src.page_generator import PageGenerator
        from figma2html.src.utils import inject_metadata
    except ImportError as e2:
        logging.error(f"figma2html 모듈 fallback import도 실패: {e2}")
        raise ImportError(f"figma2html 모듈을 import할 수 없습니다: {e}, {e2}")

router = APIRouter(prefix="/figma", tags=["figma"])

# 로거 설정
logger = logging.getLogger("app.figma")

# Request/Response 모델들
class FigmaRequest(BaseModel):
    figma_url: str
    prefer_components: bool = False  # 컴포넌트 추출 선호 여부

class FigmaUrlRequest(BaseModel):
    figma_url: str
    output_type: str = "page"  #"components", "page"

class FigmaConvertResponse(BaseModel):
    success: bool
    message: str
    file_key: str | None = None
    node_id: str | None = None
    node_name: str | None = None
    html_content: str | None = None
    css_content: str | None = None
    react_content: str | None = None
    node_type: str | None = None

class FigmaInfoResponse(BaseModel):
    success: bool
    file_key: str | None = None
    node_id: str | None = None
    is_valid_url: bool
    url_type: str  # "full_page", "specific_node", "invalid"

class FigmaProcessResponse(BaseModel):
    success: bool
    message: str
    processing_type: str  # "components", "page"
    file_key: str | None = None
    node_id: str | None = None
    node_name: str | None = None
    node_type: str | None = None
    # 컴포넌트 결과
    components: List[Dict[str, Any]] | None = None
    total_count: int | None = None
    success_count: int | None = None
    failure_count: int | None = None

@router.post("/info", response_model=FigmaInfoResponse)
async def get_figma_info(request: FigmaUrlRequest):
    """
    Figma URL 정보를 분석하고 반환
    """
    try:
        file_key, node_id = parse_figma_url(request.figma_url)
        
        if not file_key:
            return FigmaInfoResponse(
                success=False,
                is_valid_url=False,
                url_type="invalid"
            )
        
        url_type = "specific_node" if node_id else "full_page"
        
        return FigmaInfoResponse(
            success=True,
            file_key=file_key,
            node_id=node_id,
            is_valid_url=True,
            url_type=url_type
        )
    
    except Exception as e:
        logging.error(f"Figma URL 분석 오류: {str(e)}")
        raise HTTPException(status_code=400, detail=f"URL 분석 오류: {str(e)}")

# TODO: vue, svelte 추가 필요
# components 변환만을 위한 router(vue, svelte 추가 필요)
@router.post("/components", response_model=Dict[str, Any])
async def convert_figma_components(request: FigmaUrlRequest):
    """
    Figma 선택 영역의 모든 컴포넌트를 React TSX로 변환
    main.py의 convert_react_selection 로직을 기반으로 함
    """
    try:
        logger.info("🔄 Figma 노드 선택의 모든 컴포넌트를 React로 변환 중...")
        
        # 1. Figma API 토큰 확인
        figma_token = os.getenv("FIGMA_API_TOKEN")
        if not figma_token:
            raise HTTPException(status_code=500, detail="FIGMA_API_TOKEN이 설정되지 않았습니다")
        
        # 2. Figma URL 파싱
        file_key, node_id = parse_figma_url(request.figma_url)
        if not file_key:
            raise HTTPException(status_code=400, detail="잘못된 Figma URL입니다")
        
        if not node_id:
            raise HTTPException(
                status_code=400, 
                detail="node-id가 필요합니다. 특정 노드를 선택해주세요"
            )
        
        logger.info(f"📂 파일 키: {file_key}")
        logger.info(f"🎯 노드 ID: {node_id}")
        
        # 3. 특정 노드 데이터 가져오기
        logger.info("🔄 선택된 노드 데이터 가져오는 중...")
        with tempfile.TemporaryDirectory() as temp_dir:
            converter = FigmaToCode(figma_token)
            raw_nodes, node_name = converter._fetch_figma_data(file_key, node_id)
            
            if not raw_nodes:
                logger.error("❌ Figma 노드 데이터를 가져오는데 실패했습니다")
                raise HTTPException(status_code=500, detail="Figma 노드 데이터를 가져오는데 실패했습니다")
            
            logger.info("✅ Figma 노드 데이터 가져오기 성공")
            logger.info(f"📝 선택된 노드: '{node_name}'")
            
            # 4. 선택된 노드에서 모든 컴포넌트 추출 (항상 filter_components=True)
            from figma2html.src.main import _extract_all_nodes_from_selection
            selected_node = raw_nodes[0]
            all_nodes = _extract_all_nodes_from_selection(selected_node, filter_components=True)
            
            if not all_nodes:
                logger.warning("⚠️ 처리할 컴포넌트가 없습니다")
                return {
                    "success": True,
                    "message": "처리할 컴포넌트가 없습니다 (COMPONENT/INSTANCE 타입만 필터링됨)",
                    "file_key": file_key,
                    "node_id": node_id,
                    "selected_node_name": node_name,
                    "components": [],
                    "total_count": 0,
                    "success_count": 0,
                    "failure_count": 0
                }
            
            logger.info(f"🎯 찾은 컴포넌트 수: {len(all_nodes)}개")
            
            # 5. 각 컴포넌트별로 React 컴포넌트 생성
            generator = ReactComponentGenerator()
            components = []
            success_count = 0
            failure_count = 0
            
            for i, node in enumerate(all_nodes, 1):
                node_name_current = node.get("name", f"Component_{i}")
                node_type = node.get("type", "UNKNOWN")
                
                logger.info(f"🔄 [{i}/{len(all_nodes)}] {node_type}: '{node_name_current}' 처리 중...")
                
                try:
                    # 메타데이터 주입
                    from figma2html.src.utils import inject_metadata
                    inject_metadata(node, file_key, node_id)
                    
                    success, message = await generator.generate_component(node, temp_dir)
                    
                    component_info = {
                        "name": node_name_current,
                        "type": node_type,
                        "success": success,
                        "message": message,
                        "component_name": generator.component_name if success else None,
                        "width": node.get("width", 0),
                        "height": node.get("height", 0)
                    }
                    
                    # 생성된 파일 내용도 포함
                    if success:
                        try:
                            component_file = f"{generator.component_name}.tsx"
                            component_path = os.path.join(temp_dir, component_file)
                            if os.path.exists(component_path):
                                with open(component_path, 'r', encoding='utf-8') as f:
                                    component_info["code"] = f.read()
                        except Exception as e:
                            logger.warning(f"컴포넌트 파일 읽기 실패: {e}")
                        
                        logger.info(f"✅ {generator.component_name} 생성 완료")
                        success_count += 1
                    else:
                        logger.error(f"❌ {node_name_current} 생성 실패: {message}")
                        failure_count += 1
                    
                    components.append(component_info)
                    
                except Exception as e:
                    logger.error(f"❌ {node_name_current} 처리 중 오류: {e}")
                    failure_count += 1
                    components.append({
                        "name": node_name_current,
                        "type": node_type,
                        "success": False,
                        "message": f"처리 중 오류: {str(e)}",
                        "component_name": None,
                        "width": node.get("width", 0),
                        "height": node.get("height", 0)
                    })
            
            # 6. 결과 요약
            logger.info("🎉 선택 노드 변환 완료!")
            logger.info(f"📊 성공: {success_count}개, 실패: {failure_count}개")
            
            if success_count > 0:
                logger.info("💡 컴포넌트가 성공적으로 생성되었습니다")
            
            return {
                "success": True,
                "message": f"컴포넌트 변환 완료: 성공 {success_count}개, 실패 {failure_count}개",
                "file_key": file_key,
                "node_id": node_id,
                "selected_node_name": node_name,
                "components": components,
                "total_count": len(all_nodes),
                "success_count": success_count,
                "failure_count": failure_count,
                "filter_applied": "COMPONENT/INSTANCE 타입만 필터링됨"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"컴포넌트 변환 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"컴포넌트 변환 중 오류: {str(e)}")


# 페이지 변환만을 위해 필요한 것 (옵션 vue, svelte)
# TODO: components & page 변환 한꺼번에 하는게 필요할지도,,?
@router.post("/convert", response_model=FigmaConvertResponse)
async def convert_figma(request: FigmaUrlRequest, background_tasks: BackgroundTasks):
    """
    Figma 디자인을 React 컴포넌트, 또는 페이지로 변환
    """
    try:
        # Figma API 토큰 확인
        figma_token = os.getenv("FIGMA_API_TOKEN")
        if not figma_token:
            raise HTTPException(
                status_code=500, 
                detail="FIGMA_API_TOKEN이 설정되지 않았습니다"
            )
        
        # URL 파싱
        file_key, node_id = parse_figma_url(request.figma_url)
        if not file_key:
            raise HTTPException(status_code=400, detail="잘못된 Figma URL입니다")
        
        # 임시 디렉토리 생성
        with tempfile.TemporaryDirectory() as temp_dir:
            converter = FigmaToCode(figma_token)
            
            # if request.output_type == "html":
            #     # HTML/CSS 변환
            #     success, message, html_content, css_content, node_name = converter.convert_from_url(
            #         request.figma_url, temp_dir
            #     )
                
            #     if not success:
            #         raise HTTPException(status_code=500, detail=message)
                
            #     return FigmaConvertResponse(
            #         success=True,
            #         message="HTML/CSS 변환 성공",
            #         file_key=file_key,
            #         node_id=node_id,
            #         node_name=node_name,
            #         html_content=html_content,
            #         css_content=css_content
            #     )
            
            if request.output_type == "components":
                # React 컴포넌트 변환
                if not node_id:
                    raise HTTPException(
                        status_code=400, 
                        detail="React 컴포넌트 변환에는 특정 노드 선택이 필요합니다"
                    )
                
                raw_nodes, node_name = converter._fetch_figma_data(file_key, node_id)
                if not raw_nodes:
                    raise HTTPException(status_code=500, detail="Figma 데이터를 가져올 수 없습니다")
                
                generator = ReactComponentGenerator()
                first_node = raw_nodes[0]
                
                # 노드 타입 확인
                node_type = first_node.get("type", "UNKNOWN")
                
                success, react_message = await generator.generate_component(first_node, temp_dir)
                if not success:
                    raise HTTPException(status_code=500, detail=react_message)
                
                # 생성된 React 파일 읽기
                react_content = None
                try:
                    component_files = [f for f in os.listdir(temp_dir) if f.endswith('.tsx')]
                    if component_files:
                        with open(os.path.join(temp_dir, component_files[0]), 'r', encoding='utf-8') as f:
                            react_content = f.read()
                except Exception as e:
                    logging.warning(f"React 파일 읽기 실패: {e}")
                
                return FigmaConvertResponse(
                    success=True,
                    message=f"React 컴포넌트 '{generator.component_name}' 변환 성공",
                    file_key=file_key,
                    node_id=node_id,
                    node_name=node_name,
                    react_content=react_content,
                    node_type=node_type
                )
            
            elif request.output_type == "page":
                # 페이지 변환 (HTML/CSS + React TSX)
                success, message, html_content, css_content, node_name = converter.convert_from_url(
                    request.figma_url, temp_dir
                )
                
                if not success:
                    raise HTTPException(status_code=500, detail=message)
                
                # TSX 페이지 생성
                generator = PageGenerator()
                tsx_success, tsx_content = await generator.generate_layout_with_llm(
                    html_content, css_content, temp_dir
                )
                
                return FigmaConvertResponse(
                    success=True,
                    message="페이지 변환 성공",
                    file_key=file_key,
                    node_id=node_id,
                    node_name=node_name,
                    html_content=html_content,
                    css_content=css_content,
                    react_content=tsx_content if tsx_success else None
                )
            
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="지원되지 않는 output_type입니다. 'html', 'react', 'page' 중 선택하세요"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Figma 변환 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"변환 중 오류 발생: {str(e)}")



@router.post("/process", response_model=FigmaProcessResponse)
async def process_figma(request: FigmaRequest):
    """
    Figma URL을 분석하고 적절한 처리 방식을 자동 결정
    채팅 시스템에서 사용하는 통합 엔드포인트
    """
    try:
        # Figma API 토큰 확인
        figma_token = os.getenv("FIGMA_API_TOKEN")
        if not figma_token:
            raise HTTPException(status_code=500, detail="FIGMA_API_TOKEN이 설정되지 않았습니다")
        
        # 1. URL 파싱
        file_key, node_id = parse_figma_url(request.figma_url)
        if not file_key:
            raise HTTPException(status_code=400, detail="잘못된 Figma URL입니다")
        
        converter = FigmaToCode(figma_token)
        
        if not node_id:
            # 전체 페이지 처리
            return await _process_full_page(converter, request.figma_url, file_key)
        
        # 2. 특정 노드 정보 분석
        raw_nodes, node_name = converter._fetch_figma_data(file_key, node_id)
        if not raw_nodes:
            raise HTTPException(status_code=500, detail="Figma 데이터를 가져올 수 없습니다")
        
        node_info = raw_nodes[0]
        node_type = node_info.get("type", "UNKNOWN")
        
        return await _process_components(
            converter, request.figma_url, file_key, node_id, node_name, node_type
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Figma 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"처리 중 오류 발생: {str(e)}")

async def _process_full_page(converter: FigmaToCode, figma_url: str, file_key: str) -> FigmaProcessResponse:
    """전체 페이지 처리"""
    with tempfile.TemporaryDirectory() as temp_dir:
        success, message, html_content, css_content, node_name = converter.convert_from_url(
            figma_url, temp_dir
        )
        
        if not success:
            raise HTTPException(status_code=500, detail=message)
        
        return FigmaProcessResponse(
            success=True,
            message="전체 페이지 변환 성공",
            processing_type="page",
            file_key=file_key,
            node_name=node_name,
            html_content=html_content,
            css_content=css_content
        )

async def _process_components(
    converter: FigmaToCode,
    figma_url: str,
    file_key: str,
    node_id: str,
    node_name: str,
    node_type: str
) -> FigmaProcessResponse:
    """컴포넌트 처리"""
    with tempfile.TemporaryDirectory() as temp_dir:
        raw_nodes, _ = converter._fetch_figma_data(file_key, node_id)
        
        from figma2html.src.main import _extract_all_nodes_from_selection
        selected_node = raw_nodes[0]
        all_nodes = _extract_all_nodes_from_selection(selected_node, filter_components=True)
        
        generator = ReactComponentGenerator()
        components = []
        success_count = 0
        failure_count = 0
        
        for i, node in enumerate(all_nodes):
            try:
                inject_metadata(node, file_key, node_id)
                success, message = await generator.generate_component(node, temp_dir)
                
                component_info = {
                    "name": node.get("name", f"Component_{i+1}"),
                    "type": node.get("type", "UNKNOWN"),
                    "success": success,
                    "message": message,
                    "component_name": generator.component_name if success else None
                }
                
                if success:
                    try:
                        component_file = f"{generator.component_name}.tsx"
                        component_path = os.path.join(temp_dir, component_file)
                        if os.path.exists(component_path):
                            with open(component_path, 'r', encoding='utf-8') as f:
                                component_info["code"] = f.read()
                    except Exception as e:
                        logging.warning(f"컴포넌트 파일 읽기 실패: {e}")
                    
                    success_count += 1
                else:
                    failure_count += 1
                
                components.append(component_info)
                
            except Exception as e:
                failure_count += 1
                components.append({
                    "name": node.get("name", f"Component_{i+1}"),
                    "type": node.get("type", "UNKNOWN"),
                    "success": False,
                    "message": f"처리 중 오류: {str(e)}"
                })
        
        return FigmaProcessResponse(
            success=True,
            message=f"컴포넌트 변환 완료: 성공 {success_count}개, 실패 {failure_count}개",
            processing_type="components",
            file_key=file_key,
            node_id=node_id,
            node_name=node_name,
            node_type=node_type,
            components=components,
            total_count=len(all_nodes),
            success_count=success_count,
            failure_count=failure_count
        )