from fastapi import APIRouter, Depends
from figma2code.generate_page.controller.dto.generate_page_dto import (
    FigmaConvertResponseDTO,
    FigmaCreatePageRequestDTO,
)
from figma2code.generate_page.service.generate_page_service import (
    GeneratePageService,
    get_generate_page_service,
)

router = APIRouter(prefix="/generate_page", tags=["generate_page"])


@router.post("/generate", response_model=FigmaConvertResponseDTO)
async def generate(
    body: FigmaCreatePageRequestDTO,
    service: GeneratePageService = Depends(get_generate_page_service),
) -> FigmaConvertResponseDTO:
    success, message = await service.generate(
        figma_url=body.figma_url,
        output=body.output,
        pages=body.pages,
        token=body.token,
        components=body.components,
        embed_shapes=body.embed_shapes,
    )
    return FigmaConvertResponseDTO(success=success, message=message)
