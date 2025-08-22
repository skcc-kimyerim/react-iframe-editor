import json
import pytest
from importlib import import_module


@pytest.mark.asyncio
async def test_generate_component_success(monkeypatch, tmp_path):
    mod_service = import_module(
        "figma2code.generate_component.service.generate_component_service"
    )
    GenerateComponentService = getattr(mod_service, "GenerateComponentService")

    service = GenerateComponentService()

    # parse_figma_url -> (file_key, node_id)
    mod = import_module(
        "figma2code.generate_component.service.generate_component_service"
    )
    monkeypatch.setattr(mod, "parse_figma_url", lambda url: ("file_key", "1:2"))

    # Stub _fetch_figma_data to provide a COMPONENT node
    async def fake_fetch(
        self, api_client, html_generator, file_key, node_id, embed_shapes
    ):
        node = {
            "id": "1:2",
            "type": "COMPONENT",
            "name": "Button",
            "width": 20,
            "height": 20,
            "children": [],
        }
        return [node], "Button"

    monkeypatch.setattr(GenerateComponentService, "_fetch_figma_data", fake_fetch)

    # Stub ReactComponentGenerator methods
    mod_react = import_module("figma2code.common.figma2react.react_generator")
    ReactComponentGenerator = getattr(mod_react, "ReactComponentGenerator")

    async def fake_find(
        self,
        selection_document,
        guide_md_path="./output/frontend/COMPONENTS_GUIDE.md",
        filter_components=False,
        concurrency=5,
    ):
        return True, {
            "results": [
                {
                    "nodeName": "Button",
                    "nodeType": "COMPONENT",
                    "decision": {
                        "index": -1,
                        "name": "button",
                        "reason": "no similar one",
                    },
                    "__component": selection_document,
                }
            ],
            "components": {},
        }

    def fake_is_similar(self, selection_result):
        return True, {"similar": [], "new": selection_result.get("results", [])}

    async def fake_gen(self, document, output_dir):
        return True, f"{output_dir}/Button.tsx"

    async def fake_gen_ref(self, document, output_dir, reference_sources):
        return True, f"{output_dir}/Button.tsx"

    # Avoid real LLM client initialization in __init__
    def fake_init(self):
        self.component_name = ""
        self.llm_service = object()

    monkeypatch.setattr(ReactComponentGenerator, "__init__", fake_init)
    monkeypatch.setattr(
        ReactComponentGenerator, "find_similar_component_in_selection", fake_find
    )
    monkeypatch.setattr(
        ReactComponentGenerator, "_is_similar_component", fake_is_similar
    )
    monkeypatch.setattr(ReactComponentGenerator, "_generate_react_component", fake_gen)
    monkeypatch.setattr(
        ReactComponentGenerator,
        "_generate_react_component_with_reference",
        fake_gen_ref,
    )

    ok, message = await service.generate(
        "https://www.figma.com/design/x?node-id=1-2",
        output=str(tmp_path),
        token="token",
        embed_shapes=False,
    )

    assert ok is True
    payload = json.loads(message)
    assert "new" in payload or "similar" in payload


@pytest.mark.asyncio
async def test_generate_component_invalid_url(monkeypatch, tmp_path):
    mod_service = import_module(
        "figma2code.generate_component.service.generate_component_service"
    )
    GenerateComponentService = getattr(mod_service, "GenerateComponentService")

    service = GenerateComponentService()

    mod = import_module(
        "figma2code.generate_component.service.generate_component_service"
    )
    monkeypatch.setattr(mod, "parse_figma_url", lambda url: (None, None))

    ok, msg = await service.generate("bad-url", output=str(tmp_path), token="t")

    assert ok is False
    assert ("잘못된" in msg) or ("Figma" in msg)
