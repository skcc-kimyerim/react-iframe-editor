"""
이미지 처리 유틸리티 함수들
"""
import base64
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger("app.chat.image")


async def encode_image_to_base64(image_path: str) -> Optional[str]:
    """로컬 이미지 파일을 base64로 인코딩"""
    try:
        path = Path(image_path)
        if not path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return None
        
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to encode image {image_path}: {e}")
        return None


async def download_and_encode_image(url: str) -> Optional[str]:
    """URL에서 이미지를 다운로드하고 base64로 인코딩"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return base64.b64encode(response.content).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to download and encode image from {url}: {e}")
        return None


def get_image_media_type(url: str) -> str:
    """URL이나 파일 경로에서 이미지 미디어 타입 추정"""
    url_lower = url.lower()
    if url_lower.endswith('.png'):
        return 'image/png'
    elif url_lower.endswith('.jpg') or url_lower.endswith('.jpeg'):
        return 'image/jpeg'
    elif url_lower.endswith('.gif'):
        return 'image/gif'
    elif url_lower.endswith('.webp'):
        return 'image/webp'
    else:
        return 'image/jpeg'  # 기본값


async def process_attachment_for_claude(attachment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """첨부 파일을 Claude API 형식으로 변환"""
    from app.core.config import settings
    
    url = attachment.get("url")
    mime = attachment.get("mime", "")
    filename = attachment.get("filename", "")
    
    if not url:
        return None
    
    # 이미지인 경우 base64 인코딩
    if mime.startswith("image/"):
        base64_data = None
        
        if url.startswith("http"):
            # 외부 URL에서 다운로드
            base64_data = await download_and_encode_image(url)
        elif url.startswith("/api/uploads/"):
            # 로컬 업로드 파일 - URL에서 파일명 추출하여 업로드 디렉토리에서 찾기
            file_id = url.split("/")[-1]  # /api/uploads/filename.ext에서 filename.ext 추출
            local_path = settings.UPLOAD_DIR / file_id
            base64_data = await encode_image_to_base64(str(local_path))
        else:
            # 기타 로컬 파일
            base64_data = await encode_image_to_base64(url)
        
        if not base64_data:
            return {
                "type": "text", 
                "text": f"[이미지 로딩 실패: {filename or url}]"
            }
        
        media_type = mime if mime.startswith("image/") else get_image_media_type(url)
        
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64_data
            }
        }
    
    # 텍스트 파일인 경우 (MD, TXT 등) 내용 읽기
    elif mime in ["text/markdown", "text/plain", "application/pdf"]:
        try:
            file_content = await extract_text_content(url, mime)
            if file_content:
                return {
                    "type": "text",
                    "text": f"[파일: {filename}]\n\n{file_content}"
                }
        except Exception as e:
            logger.warning(f"텍스트 파일 처리 실패 ({filename}): {e}")
    
    # 기타 파일은 파일 정보만 제공
    return {
        "type": "text",
        "text": f"[첨부 파일: {filename or url} ({mime})]"
    }


async def extract_text_content(url: str, mime: str) -> Optional[str]:
    """텍스트 파일의 내용을 추출합니다."""
    from app.core.config import settings
    import asyncio
    
    try:
        if url.startswith("/api/uploads/"):
            # 로컬 업로드 파일
            file_id = url.split("/")[-1]
            local_path = settings.UPLOAD_DIR / file_id
            
            if not local_path.exists():
                return None
            
            if mime == "application/pdf":
                # PDF 파일 처리 (PyPDF2 또는 pdfplumber 사용)
                return await extract_pdf_text(str(local_path))
            else:
                # 텍스트 파일 (MD, TXT 등)
                return local_path.read_text(encoding="utf-8")
        
        return None
        
    except Exception as e:
        logger.error(f"텍스트 추출 실패: {e}")
        return None


async def extract_pdf_text(pdf_path: str) -> Optional[str]:
    """PDF 파일에서 텍스트를 추출합니다."""
    try:
        # PyPDF2를 사용한 PDF 텍스트 추출
        import PyPDF2
        import asyncio
        
        def _extract_pdf():
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()
                return text
        
        # 비동기적으로 실행
        text = await asyncio.get_event_loop().run_in_executor(None, _extract_pdf)
        return text.strip() if text else None
        
    except ImportError:
        logger.warning("PyPDF2가 설치되지 않았습니다. pip install PyPDF2")
        return None
    except Exception as e:
        logger.error(f"PDF 텍스트 추출 실패: {e}")
        return None