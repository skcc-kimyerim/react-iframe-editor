import pytest
from importlib import import_module


@pytest.mark.asyncio
async def test_convert_html_success(monkeypatch, tmp_path):
    mod_service = import_module("figma2code.convert_html.service.convert_html_service")
    ConvertHtmlService = getattr(mod_service, "ConvertHtmlService")
    service = ConvertHtmlService()

    # parse_figma_url -> (file_key, node_id)
    mod = import_module("figma2code.convert_html.service.convert_html_service")
    monkeypatch.setattr(mod, "parse_figma_url", lambda url: ("file_key", "1:2"))

    # Stub _fetch_figma_data to avoid network
    sample_nodes = [
        {
            "id": "1:2",
            "type": "FRAME",
            "name": "Root",
            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 100, "height": 100},
            "visible": True,
            "children": [],
        }
    ]

    async def fake_fetch(
        self, api_client, html_generator, file_key, node_id, embed_shapes
    ):
        return sample_nodes, "Root"

    monkeypatch.setattr(ConvertHtmlService, "_fetch_figma_data", fake_fetch)

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
        return {"html": "<div>OK</div>", "css": "/* css */"}

    monkeypatch.setattr(HtmlGenerator, "html_main", fake_html_main, raising=True)

    # Stub _save_output_files to avoid file IO
    def fake_save(self, html, css, node_name, output_dir, stats):
        return True, f"{output_dir}/saved"

    monkeypatch.setattr(ConvertHtmlService, "_save_output_files", fake_save)

    ok, msg = await service.convert(
        "https://www.figma.com/design/x?node-id=1-2",
        output_dir=str(tmp_path),
        token="token",
        embed_shapes=False,
    )

    assert ok is True
    assert "saved" in msg


@pytest.mark.asyncio
async def test_convert_html_invalid_url(monkeypatch):
    mod_service = import_module("figma2code.convert_html.service.convert_html_service")
    ConvertHtmlService = getattr(mod_service, "ConvertHtmlService")
    service = ConvertHtmlService()

    mod = import_module("figma2code.convert_html.service.convert_html_service")
    monkeypatch.setattr(mod, "parse_figma_url", lambda url: (None, None))

    ok, msg = await service.convert("bad-url", output_dir="out", token="token")

    assert ok is False
    assert ("잘못된" in msg) or ("Figma" in msg)
