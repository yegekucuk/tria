import hashlib
import re
from pathlib import Path
from datetime import datetime
from markdown_it import MarkdownIt

from src.data_models import Document


class BaseParser:
    """Base parser interface"""
    def parse(self, path: Path, content: str) -> Document:
        doc_id = hashlib.sha1(f"{path}{content}".encode()).hexdigest()[:16]
        lines = content.count('\n') + 1 if content else 0
        
        return Document(
            id=doc_id,
            path=str(path),
            language=self.get_language(path),
            size_bytes=len(content.encode()),
            lines=lines,
            content=content,
            meta={
                "last_modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None
            }
        )
    
    def get_language(self, path: Path) -> str:
        return "unknown"

class PythonParser(BaseParser):
    def get_language(self, path: Path) -> str:
        return "python"
    
    def parse(self, path: Path, content: str) -> Document:
        doc = super().parse(path, content)
        # Extract functions and classes for metadata
        functions = re.findall(r'def\s+(\w+)\s*\(', content)
        classes = re.findall(r'class\s+(\w+)\s*[\(:]', content)
        # Remove duplicates
        functions = list(set(functions))
        classes = list(set(classes))
        doc.meta.update({
            "functions": functions,
            "classes": classes
        })
        return doc


class JavaScriptParser(BaseParser):
    IDENTIFIER_RE = r'[A-Za-z_$][A-Za-z0-9_$]*'

    FUNCTION_PATTERNS = (
        rf'\bfunction\s+({IDENTIFIER_RE})\s*(?:<[^>\n]+>)?\s*\(',
        rf'\b(?:const|let|var)\s+({IDENTIFIER_RE})(?:\s*:\s*[^\n=]+)?\s*=\s*(?:async\s*)?function\b',
        rf'\b(?:const|let|var)\s+({IDENTIFIER_RE})(?:\s*:\s*[^\n=]+)?\s*=\s*(?:async\s*)?(?:\([^)]*\)|{IDENTIFIER_RE})\s*(?::\s*[^\n=]+)?=>',
    )

    CLASS_PATTERN = rf'\bclass\s+({IDENTIFIER_RE})\b'

    def get_language(self, path: Path) -> str:
        return "javascript"

    def parse(self, path: Path, content: str) -> Document:
        doc = super().parse(path, content)
        functions = []
        for pattern in self.FUNCTION_PATTERNS:
            functions.extend(re.findall(pattern, content))
        classes = re.findall(self.CLASS_PATTERN, content)

        doc.meta.update({
            "functions": sorted(set(functions)),
            "classes": sorted(set(classes)),
        })
        return doc


class TypeScriptParser(JavaScriptParser):
    def get_language(self, path: Path) -> str:
        return "typescript"

class MarkdownParser(BaseParser):
    def get_language(self, path: Path) -> str:
        return "markdown"

    def parse(self, path: Path, content: str) -> Document:
        doc = super().parse(path, content)
        md = MarkdownIt()
        tokens = md.parse(content)
        headers = []
        for i, token in enumerate(tokens):
            if token.type == "heading_open":
                # heading_open -> heading_close arasındaki inline token text'ini al
                next_token = tokens[i + 1]
                if next_token.type == "inline":
                    headers.append(next_token.content)
        doc.meta["headers"] = headers
        doc.meta["content"] = content
        return doc
    
class DockerfileParser(BaseParser):
    def get_language(self, path: Path) -> str:
        return "dockerfile"
    
    def parse(self, path: Path, content: str) -> Document:
        doc = super().parse(path, content)
        image = None
        workdir = None
        entrypoint = None
        cmd = None
        env = {}
        # Go throught the content and extract information
        for line in content.splitlines():
            line = line.strip()
            upper_line = line.upper()
            if upper_line.startswith('FROM ') and not image:
                image = line[5:].split(' AS ')[0].strip()
            elif upper_line.startswith('WORKDIR '):
                workdir = line[8:].strip()
            elif upper_line.startswith('ENTRYPOINT '):
                entrypoint = line[11:].strip()
            elif upper_line.startswith('CMD '):
                cmd = line[4:].strip()
            elif upper_line.startswith('ENV '):
                # Parse ENV key=value or ENV key value
                env_part = line[4:].strip()
                if '=' in env_part:
                    key, value = env_part.split('=', 1)
                    env[key.strip()] = value.strip()
                else:
                    parts = env_part.split(None, 1)
                    if len(parts) == 2:
                        env[parts[0]] = parts[1]
        doc.meta["image"] = image
        doc.meta["workdir"] = workdir
        doc.meta["entrypoint"] = entrypoint
        doc.meta["cmd"] = cmd
        doc.meta["env"] = env
        return doc

class LicenseParser(BaseParser):
    def get_language(self, path: Path) -> str:
        return "license"
    
    def parse(self, path, content):
        doc = super().parse(path, content)
        # Extract the first line (header) of the license
        doc.meta["header"] = content.splitlines()[0].strip()
        return doc

class TextParser(BaseParser):
    def get_language(self, path: Path) -> str:
        return "text"
    
class UnknownParser(BaseParser):
    def get_language(self, path: Path) -> str:
        return "unknown"

def get_parser(path: Path) -> BaseParser:
    """Returns appropriate parser based on file extension"""
    if path.name == "Dockerfile":
        return DockerfileParser()
    elif path.name == "LICENSE":
        return LicenseParser()

    ext = path.suffix.lower()
    parsers = {
        '.py': PythonParser(),
        '.js': JavaScriptParser(),
        '.jsx': JavaScriptParser(),
        '.mjs': JavaScriptParser(),
        '.cjs': JavaScriptParser(),
        '.ts': TypeScriptParser(),
        '.tsx': TypeScriptParser(),
        '.mts': TypeScriptParser(),
        '.cts': TypeScriptParser(),
        '.md': MarkdownParser(),
        '.txt': TextParser(),
    }
    return parsers.get(ext, UnknownParser())
