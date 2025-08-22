from unittest.mock import patch

from fastapi.testclient import TestClient


class TestConverterControllerE2E:
    async def test_converter_convert_e2e_with_mock(self, client: TestClient) -> None:
        # Given
        payload = {
            "figma_url": "https://www.figma.com/file/TEST?node-id=1%3A2",
            "output_dir": "output",
            "token": "test-token",
            "embed_shapes": True,
        }

        # When
        with patch(
            "figma2code.service.converter_service.ConverterService.convert",
            return_value=(True, "mock-success"),
        ):
            response = client.post("/converter/convert", json=payload)

        # Then
        assert response.status_code == 200
        assert response.json() == {"success": True, "message": "mock-success"}
