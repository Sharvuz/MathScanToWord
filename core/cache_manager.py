import os
import json
import hashlib
import re
from typing import Dict, Any, Optional, List

class CacheManager:
    def __init__(self, base_dir: str = "cache"):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def get_document_cache_dir(self, file_path: str) -> str:
        """Create a unique cache directory for a given PDF or image file based on path + file stats."""
        stats = os.stat(file_path)
        hash_input = f"{file_path}_{stats.st_size}_{stats.st_mtime}".encode('utf-8')
        doc_hash = hashlib.md5(hash_input).hexdigest()[:12]
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        # Clean folder name
        safe_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '_', '-')).strip()
        doc_dir = os.path.join(self.base_dir, f"{safe_name}_{doc_hash}")
        os.makedirs(doc_dir, exist_ok=True)
        return doc_dir

    def save_page_result(self, doc_dir: str, page_num: int, data: Dict[str, Any]):
        page_file = os.path.join(doc_dir, f"page_{page_num:04d}.json")
        with open(page_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _fix_json_latex_escapes(text: str) -> str:
        latex_cmds = (
            r'text|textbf|textit|texttt|tfrac|tan|tanh|theta|times|to|tau|top|triangle|'
            r'dfrac|frac|forall|'
            r'bar|beta|begin|binom|mathbf|boldsymbol|bullet|bot|'
            r'right|rho|rangle|rightarrow|Rightarrow|'
            r'neq|nabla|neg|notin'
        )
        pattern = rf'(?<!\\)\\({latex_cmds})\b'
        return re.sub(pattern, r'\\\\\1', text)

    def get_page_result(self, doc_dir: str, page_num: int) -> Optional[Dict[str, Any]]:
        page_file = os.path.join(doc_dir, f"page_{page_num:04d}.json")
        if os.path.exists(page_file):
            try:
                with open(page_file, "r", encoding="utf-8") as f:
                    raw = f.read()
                raw = self._fix_json_latex_escapes(raw)
                return json.loads(raw)
            except Exception:
                return None
        return None

    def get_completed_pages(self, doc_dir: str) -> List[int]:
        if not os.path.exists(doc_dir):
            return []
        pages = []
        for f in os.listdir(doc_dir):
            if f.startswith("page_") and f.endswith(".json"):
                try:
                    num_str = f.split("_")[1].split(".")[0]
                    pages.append(int(num_str))
                except ValueError:
                    pass
        return sorted(pages)

    def clear_doc_cache(self, doc_dir: str):
        if os.path.exists(doc_dir):
            import shutil
            shutil.rmtree(doc_dir, ignore_errors=True)
            os.makedirs(doc_dir, exist_ok=True)
