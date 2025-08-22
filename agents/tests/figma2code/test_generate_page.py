import pytest
from importlib import import_module


@pytest.mark.asyncio
async def test_generate_page_success(monkeypatch, tmp_path):
    mod_service = import_module(
        "figma2code.generate_page.service.generate_page_service"
    )
    GeneratePageService = getattr(mod_service, "GeneratePageService")

    service = GeneratePageService()

    # parse_figma_url -> (file_key, node_id)
    mod = import_module("figma2code.generate_page.service.generate_page_service")
    monkeypatch.setattr(mod, "parse_figma_url", lambda url: ("file_key", "1:2"))

    # Stub _fetch_figma_data to avoid network
    async def fake_fetch(
        self, api_client, html_generator, file_key, node_id, embed_shapes
    ):
        node = {
            "id": "1:2",
            "type": "FRAME",
            "name": "Main Screen",
            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 100, "height": 100},
            "children": [],
        }
        return [node], "Main Screen"

    monkeypatch.setattr(GeneratePageService, "_fetch_figma_data", fake_fetch)

    # Stub JsonNodeConverter.nodes_to_json
    mod_json = import_module("figma2code.common.figma2html.json_node_converter")
    JsonNodeConverter = getattr(mod_json, "JsonNodeConverter")

    def fake_nodes_to_json(self, nodes, settings=None):
        return nodes, {"nodes_processed": len(nodes), "groups_inlined": 0}

    monkeypatch.setattr(
        JsonNodeConverter, "nodes_to_json", fake_nodes_to_json, raising=True
    )

    # Stub HtmlGenerator.html_main
    mod_html = import_module("figma2code.common.figma2html.html_generator")
    HtmlGenerator = getattr(mod_html, "HtmlGenerator")

    def fake_html_main(self, nodes, is_preview=False):
        return {"html": "<div>Page</div>", "css": "/* css */"}

    monkeypatch.setattr(HtmlGenerator, "html_main", fake_html_main, raising=True)

    # Stub ReactComponentGenerator LLM call
    mod_react = import_module("figma2code.common.figma2react.react_generator")
    ReactComponentGenerator = getattr(mod_react, "ReactComponentGenerator")

    async def fake_llm(self, prompt):
        return "export default function MainScreenPage() { return (<div />) }"

    # Avoid real LLM client initialization in __init__
    def fake_init(self):
        self.component_name = ""
        self.llm_service = object()

    monkeypatch.setattr(ReactComponentGenerator, "__init__", fake_init)
    monkeypatch.setattr(
        ReactComponentGenerator,
        "_generate_react_from_html_css_with_prompt",
        fake_llm,
    )

    pages_dir = tmp_path / "pages"
    ok, msg = await service.generate(
        "https://www.figma.com/design/x?node-id=1-2",
        output=str(tmp_path / "html"),
        pages=str(pages_dir),
        token="token",
        components=str(tmp_path / "components"),
        embed_shapes=False,
    )

    assert ok is True
    tsx_path = pages_dir / "MainScreenPage.tsx"
    assert tsx_path.exists()


@pytest.mark.asyncio
async def test_generate_page_invalid_url(monkeypatch, tmp_path):
    mod_service = import_module(
        "figma2code.generate_page.service.generate_page_service"
    )
    GeneratePageService = getattr(mod_service, "GeneratePageService")

    service = GeneratePageService()

    mod = import_module("figma2code.generate_page.service.generate_page_service")
    monkeypatch.setattr(mod, "parse_figma_url", lambda url: (None, None))

    ok, msg = await service.generate(
        "bad-url",
        output=str(tmp_path / "html"),
        pages=str(tmp_path / "pages"),
        token="token",
    )

    assert ok is False
    assert ("잘못된" in msg) or ("Figma" in msg)
