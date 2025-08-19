import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from core.ai.azure_llm import AzureLLM
from core.config import get_setting
from core.db.database_transaction import transactional
from fastapi import Depends
from figma2code.chat.controller.dto.chat_dto import (
    ChatMessageRequestDTO,
    ChatMessageResponseDTO,
)
from figma2code.chat.domain.chat import Chat
from figma2code.chat.domain.chat_message import ChatMessage
from figma2code.chat.repository.chat_message_repository import (
    ChatMessageRepository,
    get_chat_message_repository,
)
from figma2code.chat.repository.chat_repository import (
    ChatRepository,
    get_chat_repository,
)
from figma2code.chat.service.chat_service_abc import ChatServiceABC
from figma2code.chat.service.figma2html.figma_api_client import FigmaApiClient
from figma2code.chat.service.figma2html.figma_url_parser import parse_figma_url
from figma2code.chat.service.figma2html.html_generator import HtmlGenerator
from figma2code.chat.service.figma2html.json_node_converter import JsonNodeConverter
from figma2code.chat.service.figma2html.utils import (
    get_best_frame_from_page,
    inject_metadata,
    sanitize_filename,
)
from figma2code.chat.service.figma2react.page_generator import make_filename
from figma2code.chat.service.figma2react.react_generator import (
    ReactComponentGenerator,
)
from openai.types.chat.chat_completion import ChatCompletion

settings = get_setting()


class ChatService(ChatServiceABC):
    def __init__(
        self,
        chat_repository: ChatRepository,
        chat_message_repository: ChatMessageRepository,
    ):
        self.chat_repository = chat_repository
        self.chat_message_repository = chat_message_repository

    @transactional
    async def process_chat_message(
        self,
        command: ChatMessageRequestDTO,
    ) -> ChatMessageResponseDTO:
        chat: Chat = await self.chat_repository.get_or_create_chat(
            Chat(
                id=command.chat_id,
                user_id=command.user_id,
                title=command.message,
            )
        )

        # llm 호출
        llm: AzureLLM = AzureLLM(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            deployment=settings.OPENAI_DEPLOYMENT,
            api_version=settings.OPENAI_API_VERSION,
        )

        completion: ChatCompletion = llm.generate_text(
            model=settings.OPENAI_MODEL,
            query=command.message,
        )

        chat_message: ChatMessage = (
            await self.chat_message_repository.create_chat_message(
                ChatMessage(
                    id=str(uuid.uuid4()),
                    chat_id=chat.id,
                    role="user",
                    type="text",
                    content=completion.choices[0].message.content,
                )
            )
        )

        return ChatMessageResponseDTO(
            id=chat_message.id,
            chat_id=chat_message.chat_id,
            content=chat_message.content,
        )

    async def convert(
        self,
        figma_url: str,
        output_dir: str = "output",
        token: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma 디자인을 HTML/CSS로 변환하여 파일로 저장합니다.
        main.py를 import하지 않고 figma2html 하위 모듈을 직접 사용합니다.
        """
        try:
            file_key, node_id = parse_figma_url(figma_url)
            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            # 클라이언트/컨버터/제너레이터 준비
            api_client = FigmaApiClient(token)
            json_converter = JsonNodeConverter()
            html_generator = HtmlGenerator(api_client=api_client)

            # 데이터 가져오기
            raw_nodes, node_name = await self._fetch_figma_data(
                api_client, html_generator, file_key, node_id, embed_shapes
            )
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

            # 노드 변환
            conversion_settings = {
                "embedVectors": True,
                "useColorVariables": True,
                "htmlGenerationMode": "html",
            }
            processed_nodes, conversion_stats = json_converter.nodes_to_json(
                raw_nodes, conversion_settings
            )
            if not processed_nodes:
                return False, "처리된 노드가 없습니다"

            # HTML/CSS 생성
            html_settings = {
                "embedVectors": True,
                "embedImages": True,
                "embedShapes": embed_shapes,
                "htmlGenerationMode": "html",
            }
            html_generator.settings = html_settings
            result = html_generator.html_main(processed_nodes, is_preview=False)

            html_content = result.get("html", "")
            css_content = result.get("css", "")

            # 경고 표시 (로그)
            warnings = html_generator.get_warnings()
            if warnings:
                logging.warning(f"경고: {len(warnings)}개 문제 발견")
                for warning in warnings[:3]:
                    logging.warning(f" - {warning}")

            # 파일 저장
            return self._save_output_files(
                html_content, css_content, node_name, output_dir, conversion_stats
            )

        except ValueError as e:
            # FIGMA_API_TOKEN 누락 등 설정 오류
            logging.error(f"설정 오류: {e}")
            return False, f"설정 오류: {e}"
        except Exception as e:
            logging.error(f"변환 중 오류: {e}")
            return False, f"변환 중 오류 발생: {e}"

    async def convert_react_component(
        self,
        figma_url: str,
        output: str = "output/frontend/components",
        token: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma의 특정 노드(또는 대표 프레임)를 기반으로 단일 React TSX 컴포넌트를 생성하여 저장합니다.

        반환: (성공 여부, 메시지)
        - 성공 시 메시지에는 저장 경로가 포함됩니다.
        """
        try:
            file_key, node_id = parse_figma_url(figma_url)
            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            api_client = FigmaApiClient(token)
            html_generator = HtmlGenerator(api_client=api_client)

            raw_nodes, _ = await self._fetch_figma_data(
                api_client, html_generator, file_key, node_id, embed_shapes
            )
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

            first_node = raw_nodes[0]

            generator = ReactComponentGenerator()
            component_name = generator._sanitize_component_name(
                first_node.get("name", "Component")
            )
            generator.component_name = component_name

            # 내부 async 메서드를 직접 await하여 이벤트 루프 중첩 문제를 회피
            success, message = await generator._generate_react_component(
                first_node, os.path.abspath(output)
            )
            return success, message
        except ValueError as e:
            logging.error(f"설정 오류: {e}")
            return False, f"설정 오류: {e}"
        except Exception as e:
            logging.error(f"컴포넌트 생성 중 오류: {e}")
            return False, f"컴포넌트 생성 중 오류: {e}"

    async def create_page(
        self,
        figma_url: str,
        output: str = "output",
        pages: Optional[str] = None,
        token: Optional[str] = None,
        components: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma 디자인을 기반으로 HTML/CSS를 생성하고, LLM을 사용해 완전한 TSX 페이지를 생성하여 저장합니다.

        - HTML/CSS는 output 디렉토리에 저장합니다.
        - TSX 페이지는 pages 디렉토리에 저장합니다(미지정 시 기본 경로 사용).

        반환: (성공 여부, 메시지)
        - 성공 시 메시지에는 TSX 저장 경로가 포함됩니다.
        """
        try:
            file_key, node_id = parse_figma_url(figma_url)
            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            api_client = FigmaApiClient(token)
            json_converter = JsonNodeConverter()
            html_generator = HtmlGenerator(api_client=api_client)

            raw_nodes, node_name = await self._fetch_figma_data(
                api_client, html_generator, file_key, node_id, embed_shapes
            )
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

            conversion_settings = {
                "embedVectors": True,
                "useColorVariables": True,
                "htmlGenerationMode": "html",
            }
            processed_nodes, conversion_stats = json_converter.nodes_to_json(
                raw_nodes, conversion_settings
            )
            if not processed_nodes:
                return False, "처리된 노드가 없습니다"

            html_settings = {
                "embedVectors": True,
                "embedImages": True,
                "embedShapes": embed_shapes,
                "htmlGenerationMode": "html",
            }
            html_generator.settings = html_settings
            result = html_generator.html_main(processed_nodes, is_preview=False)

            html_code = result.get("html", "")
            css_code = result.get("css", "")

            # HTML/CSS 저장 (로그 및 경로 안내 목적)
            save_ok, save_msg = self._save_output_files(
                html_code, css_code, node_name, output, conversion_stats
            )
            if not save_ok:
                return False, save_msg

            # 페이지 TSX 프롬프트 구성 (PageGenerator의 로직을 서비스에 맞게 inline 구성)
            components_dir = os.path.abspath(components) if components else None

            component_list_str = ""
            component_docs = ""
            mapping_rules = ""
            usage_examples = ""

            if components_dir and os.path.exists(components_dir):
                try:
                    component_files = [
                        f for f in os.listdir(components_dir) if f.endswith(".tsx")
                    ]
                except Exception:
                    component_files = []

                component_list = [f[:-4] for f in component_files]
                component_list_str = ", ".join(component_list)

                docs_blocks: List[str] = []
                for filename in component_files:
                    path = os.path.join(components_dir, filename)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            code = f.read()

                        interfaces = re.findall(
                            r"(interface [A-Za-z0-9_]+(?:Props)?\s*\{[\s\S]*?\n\})",
                            code,
                        )
                        types = re.findall(
                            r"(type [A-Za-z0-9_]+(?:Props)?\s*=\s*\{[\s\S]*?\n\})",
                            code,
                        )
                        all_definitions = interfaces + types

                        if all_definitions:
                            full_docs = "\n".join(all_definitions)
                            docs_blocks.append(f"[{filename}]\n{full_docs}\n")
                        else:
                            match = re.search(
                                r"(function [A-Za-z0-9_]+\([\s\S]+?\))",
                                code,
                            )
                            if match:
                                docs_blocks.append(f"[{filename}]\n{match.group(1)}\n")
                            else:
                                lines = code.splitlines()
                                docs_blocks.append(
                                    f"[{filename}]\n" + "\n".join(lines[:40]) + "\n"
                                )
                    except Exception as e:
                        docs_blocks.append(f"[{filename}]\n(문서 추출 실패: {e})\n")

                component_docs = "[components props/type docs]\n" + "\n".join(
                    docs_blocks
                )

                components_dir_name = os.path.basename(components_dir)

                mapping_rules = (
                    "아래 HTML 구조에서 class명, 텍스트, 계층, placeholder, label 등을 참고해서 "
                    f"{components_dir_name}/에 이미 존재하는 컴포넌트로 적극적으로 매핑해줘.\n"
                    "매핑 규칙 예시:\n"
                    "- class에 'button'이 포함되어 있고, 내부 텍스트가 'confirm', 'Send message' 등인 경우: Button 컴포넌트로 대체\n"
                    "- class에 'field', 'input'이 포함되어 있고, 내부에 'Email', 'Password' 등 텍스트가 있으면: Input 컴포넌트로 대체\n"
                    "- class에 'textarea'가 포함되어 있고, 내부에 'Type your message here' 등 placeholder가 있으면: Textarea 컴포넌트로 대체\n"
                    "이외에도, label/placeholder/텍스트/계층 정보를 적극적으로 활용해서 컴포넌트로 매핑해줘.\n"
                    f"import는 반드시 {components_dir_name}/에서 하고, 나머지는 tailwindcss로 만들어도 돼.\n"
                )

                usage_examples = (
                    "각 컴포넌트는 placeholder, value, onChange, type 등 props를 적극적으로 활용해줘.\n"
                    "중요: onChange는 (value: string) => void 타입이므로 e.target.value 대신 value를 직접 사용해줘.\n"
                    "Button은 onClick 등 이벤트 핸들러도 추가해줘.\n"
                    "필요하다면 useState, useCallback 등 React 훅을 사용해서 state와 이벤트 핸들러도 구현해.\n"
                    "예시:\n"
                    '  <Input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} type="email" />\n'
                    "  <Button onClick={handleClick}>confirm</Button>\n"
                    '  <Textarea placeholder="Type your message here" value={message} onChange={(e) => setMessage(e.target.value)} />\n'
                    "이 코드는 실제로 동작하는 React 페이지여야 하며, 단순한 시각적 mockup이 아니어야 해.\n"
                )

                components_dir_name_for_prompt = os.path.basename(components_dir)
                prompt = (
                    "아래는 Figma에서 추출한 HTML/CSS입니다.\n"
                    f"아래 컴포넌트들은 {components_dir_name_for_prompt}/에 이미 존재하니, 반드시 import해서 적극 활용해줘: [{component_list_str}]\n"
                    f"import 할 때는 반드시 각각 개별적으로 import 해야 합니다:\n"
                    f"예시: import NavigationMenu from '../{components_dir_name_for_prompt}/NavigationMenu';\n"
                    f"절대 import {{ ... }} from '{components_dir_name_for_prompt}' 형태로 하지 마세요.\n"
                    f"{component_docs}"
                    f"{mapping_rules}"
                    f"{usage_examples}"
                    "실제 Figma와 동일한 TSX(React) 페이지를 완성해줘.\n"
                    "중요: ```tsx 같은 마크다운 코드블록을 절대 포함하지 마세요. 순수한 TSX 코드만 출력하세요.\n"
                    "중요: 무조건 figma와 동일하게 만들어지는게 중요합니다. 무조건 디자인 따라서 만들어야 합니다.\n"
                    f"HTML:\n{html_code}\n"
                    f"CSS:\n{css_code}\n"
                )
            else:
                prompt = (
                    "아래는 Figma에서 추출한 HTML/CSS입니다.\n"
                    "이 HTML/CSS를 바탕으로 완전한 React TypeScript 페이지를 생성해주세요.\n"
                    "중요 사항:\n"
                    "- TypeScript + tailwindcss 사용\n"
                    "- HTML 구조를 정확히 React 컴포넌트로 변환\n"
                    "- CSS 스타일을 tailwindcss로 변환\n"
                    "- useState, useCallback 등 필요한 React 훅 사용\n"
                    "- 실제로 동작하는 페이지로 만들어주세요\n"
                    "- ```tsx 같은 마크다운 코드블록을 절대 포함하지 마세요. 순수한 TSX 코드만 출력하세요.\n"
                    "- 무조건 figma와 동일하게 만들어지는게 중요합니다. 무조건 디자인 따라서 만들어야 합니다.\n"
                    f"HTML:\n{html_code}\n"
                    f"CSS:\n{css_code}\n"
                )

            react_generator = ReactComponentGenerator()
            try:
                tsx_code = (
                    await react_generator._generate_react_from_html_css_with_prompt(
                        prompt
                    )
                )
            except Exception as e:
                return False, f"TSX 코드 생성 실패: {e}"

            tsx_filename = make_filename(node_name)
            if pages:
                pages_dir = os.path.abspath(pages)
            else:
                pages_dir = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "output/frontend")
                )

            os.makedirs(pages_dir, exist_ok=True)
            tsx_path = os.path.join(pages_dir, tsx_filename)
            try:
                with open(tsx_path, "w", encoding="utf-8") as f:
                    f.write(tsx_code)
            except Exception as e:
                return False, f"TSX 파일 저장 중 오류: {e}"

            logging.info(f"HTML/CSS 출력 디렉토리: {os.path.abspath(output)}")
            logging.info(f"TSX 페이지 저장 경로: {tsx_path}")
            return True, f"TSX 페이지 저장 완료: {tsx_path}"

        except ValueError as e:
            logging.error(f"설정 오류: {e}")
            return False, f"설정 오류: {e}"
        except Exception as e:
            logging.error(f"페이지 생성 중 오류: {e}")
            return False, f"페이지 생성 중 오류: {e}"

    async def _fetch_figma_data(
        self,
        api_client: FigmaApiClient,
        html_generator: HtmlGenerator,
        file_key: str,
        node_id: Optional[str],
        embed_shapes: bool,
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """main.py의 _fetch_figma_data를 참고하여 데이터를 가져옵니다."""
        if node_id:
            rest_data = api_client.get_file_nodes_rest(file_key, [node_id])
            if (
                not rest_data
                or "nodes" not in rest_data
                or node_id not in rest_data["nodes"]
            ):
                return None, ""
            node_data = rest_data["nodes"][node_id]
            figma_node = node_data.get("document") if node_data else None
            if not figma_node:
                return None, ""
            node_name = figma_node.get("name", "figma_node")
            raw_nodes = [figma_node]
            for node in raw_nodes:
                inject_metadata(node, file_key, node_id)
        else:
            file_data = api_client.get_file(file_key)
            if not file_data:
                return None, ""
            document = file_data.get("document", {})
            children = document.get("children", [])
            if not children:
                return None, ""
            page = children[0]
            best_frame = get_best_frame_from_page(page)
            if best_frame:
                figma_node = best_frame
                node_name = figma_node.get("name", "figma_page")
            else:
                return None, ""
            raw_nodes = [figma_node]
            for node in raw_nodes:
                inject_metadata(node, file_key)

        # 원본 순서 정보 보존
        self._preserve_original_order(raw_nodes)

        # polygon/ellipse를 SVG로 처리
        if html_generator.svg_renderer and embed_shapes:
            try:
                raw_nodes = html_generator.svg_renderer.process_shapes_in_nodes(
                    raw_nodes, file_key
                )
            except Exception as e:
                logging.warning(f"SVG 처리 중 오류: {e}")

        return raw_nodes, node_name

    def _preserve_original_order(self, nodes: List[Dict[str, Any]]) -> None:
        """재귀적으로 원본 순서 정보를 보존"""

        def add_order_info(
            node_list: List[Dict[str, Any]], parent_name: str = "root"
        ) -> None:
            for i, node in enumerate(node_list):
                if node is not None:
                    node["_original_order"] = i
                    children = node.get("children", [])
                    if children:
                        add_order_info(children, node.get("name", "unknown"))

        add_order_info(nodes)

    def _save_output_files(
        self,
        html_content: str,
        css_content: str,
        node_name: str,
        output_dir: str,
        stats: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            frame_folder_name = sanitize_filename(node_name)
            output_path = os.path.join(output_dir, frame_folder_name)
            os.makedirs(output_path, exist_ok=True)
            complete_html = self._generate_complete_html(
                html_content, css_content, node_name
            )
            html_filename = f"{sanitize_filename(node_name)}.html"
            css_filename = f"{sanitize_filename(node_name)}.css"
            html_path = os.path.join(output_path, html_filename)
            css_path = os.path.join(output_path, css_filename)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(complete_html)
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(css_content)
            logging.info(f"HTML: {html_path}")
            logging.info(f"CSS: {css_path}")
            logging.info(
                f"성능: {stats.get('nodes_processed', 0)}개 노드 처리, {stats.get('groups_inlined', 0)}개 그룹 인라인"
            )
            return True, f"{output_path}에 성공적으로 저장되었습니다"
        except Exception as e:
            return False, f"파일 저장 중 오류: {e}"

    def _generate_complete_html(
        self, html_content: str, css_content: str, title: str
    ) -> str:
        css_filename = f"{sanitize_filename(title)}.css"
        return (
            "<!DOCTYPE html>\n"
            '<html lang="ko">\n'
            "<head>\n"
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"    <title>{title}</title>\n"
            f'    <link rel="stylesheet" href="{css_filename}">\n'
            "</head>\n"
            "<body>\n"
            f"{html_content}\n"
            "</body>\n"
            "</html>"
        )


def get_chat_service(
    chat_repository: ChatRepository = Depends(get_chat_repository),
    chat_message_repository: ChatMessageRepository = Depends(
        get_chat_message_repository
    ),
) -> ChatService:
    return ChatService(chat_repository, chat_message_repository)
