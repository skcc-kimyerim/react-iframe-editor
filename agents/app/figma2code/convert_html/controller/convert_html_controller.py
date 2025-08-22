from fastapi import APIRouter, Depends
from figma2code.convert_html.controller.dto.convert_html_dto import (
    FigmaConvertRequestDTO,
    FigmaConvertResponseDTO,
)
from figma2code.convert_html.service.convert_html_service import (
    ConvertHtmlService,
    get_convert_html_service,
)

router = APIRouter(prefix="/convert_html", tags=["convert_html"])


@router.post("/convert", response_model=FigmaConvertResponseDTO)
async def convert(
    body: FigmaConvertRequestDTO,
    service: ConvertHtmlService = Depends(get_convert_html_service),
) -> FigmaConvertResponseDTO:
    success, message = await service.convert(
        figma_url=body.figma_url,
        output_dir=body.output_dir,
        token=body.token,
        embed_shapes=body.embed_shapes,
    )
    return FigmaConvertResponseDTO(success=success, message=message)
