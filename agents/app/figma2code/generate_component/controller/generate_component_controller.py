import json
from fastapi import APIRouter, Depends
from figma2code.generate_component.controller.dto.generate_component_dto import (
    FigmaConvertResponseDTO,
    FigmaReactComponentRequestDTO,
    FigmaComponentSimilarityRequestDTO,
)
from figma2code.generate_component.service.generate_component_service import (
    GenerateComponentService,
    get_generate_component_service,
)

router = APIRouter(prefix="/generate_component", tags=["generate_component"])


@router.post("/generate", response_model=FigmaConvertResponseDTO)
async def generate(
    body: FigmaReactComponentRequestDTO,
    service: GenerateComponentService = Depends(get_generate_component_service),
) -> FigmaConvertResponseDTO:
    success, message = await service.generate(
        figma_url=body.figma_url,
        output=body.output,
        token=body.token,
        embed_shapes=body.embed_shapes,
    )
    return FigmaConvertResponseDTO(success=success, message=message)


@router.post("/find-similar", response_model=FigmaConvertResponseDTO)
async def find_similar(
    body: FigmaComponentSimilarityRequestDTO,
    service: GenerateComponentService = Depends(get_generate_component_service),
) -> FigmaConvertResponseDTO:
    success, message = await service.find_similar(
        figma_url=body.figma_url,
        token=body.token,
        embed_shapes=body.embed_shapes,
        guide_md_path=body.guide_md_path,
    )
    # message를 가능하면 파싱해서 JSON으로 반환
    parsed = None
    if isinstance(message, str):
        try:
            parsed = json.loads(message)
        except Exception:
            parsed = message
    else:
        parsed = message
    return FigmaConvertResponseDTO(success=success, message=parsed)
