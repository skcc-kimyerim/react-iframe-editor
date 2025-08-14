from fastapi import APIRouter, Depends
from figma2code.chat.controller.dto.chat_dto import (
    ChatMessageRequestDTO,
    ChatMessageResponseDTO,
    ChatRequestDTO,
    FigmaConvertRequestDTO,
    FigmaConvertResponseDTO,
    FigmaCreatePageRequestDTO,
    FigmaReactComponentRequestDTO,
)
from figma2code.chat.service.chat_service import ChatService, get_chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/completions/stream", response_model=ChatMessageResponseDTO)
async def chat_stream(
    request: ChatRequestDTO,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatMessageResponseDTO:
    """채팅 스트림 엔드포인트"""
    return await chat_service.process_chat_message(
        ChatMessageRequestDTO(
            chat_id=request.chat_id,
            user_id="1234",
            message=request.message,
        )
    )


@router.post("/convert", response_model=FigmaConvertResponseDTO)
async def convert_figma(
    body: FigmaConvertRequestDTO,
    chat_service: ChatService = Depends(get_chat_service),
) -> FigmaConvertResponseDTO:
    success, message = await chat_service.convert(
        figma_url=body.figma_url,
        output_dir=body.output_dir,
        token=body.token,
        embed_shapes=body.embed_shapes,
    )
    return FigmaConvertResponseDTO(success=success, message=message)


@router.post("/convert/react-component", response_model=FigmaConvertResponseDTO)
async def convert_react_component(
    body: FigmaReactComponentRequestDTO,
    chat_service: ChatService = Depends(get_chat_service),
) -> FigmaConvertResponseDTO:
    success, message = await chat_service.convert_react_component(
        figma_url=body.figma_url,
        output=body.output,
        token=body.token,
        embed_shapes=body.embed_shapes,
    )
    return FigmaConvertResponseDTO(success=success, message=message)


@router.post("/create-page", response_model=FigmaConvertResponseDTO)
async def create_page(
    body: FigmaCreatePageRequestDTO,
    chat_service: ChatService = Depends(get_chat_service),
) -> FigmaConvertResponseDTO:
    success, message = await chat_service.create_page(
        figma_url=body.figma_url,
        output=body.output,
        pages=body.pages,
        token=body.token,
        components=body.components,
        embed_shapes=body.embed_shapes,
    )
    return FigmaConvertResponseDTO(success=success, message=message)
