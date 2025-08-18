import logging
import re
from ..files import resolve_src_path

logger = logging.getLogger("app.chat.workflow")


def _to_pascal_case(name: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", name)
    return "".join(p.capitalize() for p in parts if p)


def _to_kebab_case(name: str) -> str:
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    s2 = re.sub(r"[^A-Za-z0-9]+", "-", s1)
    return s2.strip('-').lower()


def _ensure_route_in_app(page_relative_path: str, project_name: str = "default-project") -> None:
    try:
        app_path = resolve_src_path("client/App.tsx", project_name)
        if not app_path.exists():   
            logger.warning("App.tsx not found; skipping route injection")
            return

        try:
            text = app_path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("Failed to read App.tsx")
            return

        filename = page_relative_path.split("/")[-1]
        base, ext = (filename.rsplit(".", 1) + [""])[:2]
        component = _to_pascal_case(base)
        import_stmt = f'import {component} from "./pages/{component}";'

        if import_stmt not in text:
            lines = text.splitlines()
            last_import_idx = -1
            for idx, line in enumerate(lines):
                if line.strip().startswith("import "):
                    last_import_idx = idx
            insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0
            lines.insert(insert_at, import_stmt)
            text = "\n".join(lines)

        route_line = f'          <Route path="/{_to_kebab_case(component)}" element={{<{component} />}} />'
        if route_line not in text:
            if "<Routes>" in text and "path=\"*\"" in text:
                text = re.sub(
                    r"(\s*<Route\s+path=\"\*\"[\s\S]*?>\s*</Route>|\s*<Route\s+path=\"\*\"[\s\S]*/>\s*)",
                    route_line + "\n" + r"\1",
                    text,
                    count=1,
                )
            elif "<Routes>" in text:
                text = text.replace("<Routes>", "<Routes>\n" + route_line)

        try:
            app_path.write_text(text, encoding="utf-8")
        except Exception:
            logger.exception("Failed to write App.tsx with new route")
    except Exception:
        logger.exception("Route injection failed")

