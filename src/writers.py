from datetime import datetime
import json
from logging import Logger
from pathlib import Path
from typing import List, Optional, Any, Dict
import xml.etree.ElementTree as ET
from xml.dom import minidom

from src.data_models import Document
from src.git_analyzer import GitAnalyzer


def build_folder_structure(documents: List[Document]) -> dict:
    """Build a tree structure from document paths"""
    tree = {}
    for doc in documents:
        parts = Path(doc.path).parts
        current = tree
        for part in parts[:-1]:  # Exclude filename
            if part not in current:
                current[part] = {}
            current = current[part]
        # Add file to final directory
        if parts:
            current[parts[-1]] = None
    return tree

def log_tree(logger:Logger, tree):
    logger.debug(f"Project structure: {tree}")

def format_tree_md(tree: dict, prefix: str = "", is_last: bool = True) -> List[str]:
    """Format tree structure for markdown"""
    lines = []
    items = list(tree.items())
    for i, (name, subtree) in enumerate(items):
        is_last_item = i == len(items) - 1
        connector = "└── " if is_last_item else "├── "
        lines.append(f"{prefix}{connector}{name}")
        if subtree is not None:  # Directory
            extension = "    " if is_last_item else "│   "
            lines.extend(format_tree_md(subtree, prefix + extension, is_last_item))
    return lines


class MarkdownWriter:
    """Writes output in Markdown format"""
    def __init__(self, logger:Logger):
        self.logger = logger
    
    def write(self, repo_path: str, documents: List[Document], output_path: str, 
              git_analyzer: Optional[GitAnalyzer] = None, commits_limit: int = 20):
        """Generate markdown output"""
        content = []
        content.append(f"# Repo Summary: {Path(repo_path).absolute().name}\n")
        content.append(f"**Generated:** {datetime.now().isoformat()}  ")
        content.append(f"**Files processed:** {len(documents)}\n")
        
        # Add Git History Section
        if git_analyzer and git_analyzer.is_git_repo:
            content.append("## Git History\n")
            
            # Summary
            summary = git_analyzer.get_summary()
            content.append(f"**Current Branch:** {summary.get('current_branch', 'N/A')}  ")
            content.append(f"**Total Commits:** {summary.get('total_commits', 0)}  ")
            content.append(f"**Contributors:** {summary.get('total_contributors', 0)}  ")
            if summary.get('first_commit_date'):
                content.append(f"**First Commit:** {summary['first_commit_date']}  ")
            if summary.get('last_commit_date'):
                content.append(f"**Last Commit:** {summary['last_commit_date']}  ")
            content.append("")
            
            # Branches
            branches = git_analyzer.get_branches()
            if branches:
                content.append("### Branches\n")
                for branch in branches[:10]:  # Limit to 10
                    marker = "* " if branch.is_current else "- "
                    content.append(f"{marker}**{branch.name}** (Last: {branch.last_commit}, {branch.last_commit_date.strftime('%Y-%m-%d')})")
                content.append("")
            
            # Recent Commits
            commits = git_analyzer.get_commits(limit=commits_limit)
            if commits:
                content.append("### Recent Commits\n")
                for commit in commits:
                    content.append(f"- **{commit.hash}** - {commit.message}")
                    content.append(f"  *{commit.author}* on {commit.date.strftime('%Y-%m-%d %H:%M')}")
                    if commit.files_changed > 0:
                        content.append(f"  {commit.files_changed} files: +{commit.insertions}/-{commit.deletions}")
                content.append("")
            
            # Contributors
            contributors = git_analyzer.get_contributors()
            if contributors:
                content.append("### Contributors\n")
                for contrib in contributors[:10]:  # Top 10
                    content.append(f"- **{contrib.name}** ({contrib.email})")
                    content.append(f"  {contrib.commits} commits, +{contrib.insertions}/-{contrib.deletions}")
                content.append("")
        
        # Add folder structure
        content.append("## Folder Structure\n")
        content.append("```")
        tree = build_folder_structure(documents)
        log_tree(self.logger, tree)
        content.extend(format_tree_md(tree))
        content.append("```\n")
        
        content.append("## Files\n")
        
        for doc in documents:
            content.append(f"### {doc.path}")
            content.append(f"*Language:* {doc.language}  ")
            content.append(f"*Size:* {doc.size_bytes} bytes, {doc.lines} lines  ")

            # Add metadata
            if doc.language == "python":
                if doc.meta.get("classes", []):
                    content.append(f"*Classes:* {', '.join(doc.meta['classes'])}  ")
                if doc.meta.get("functions", []):
                    content.append(f"*Functions:* {', '.join(doc.meta['functions'])}  ")
            elif doc.language == "markdown":
                if doc.meta.get("headers", []):
                    content.append(f"*Headers:* {', '.join(doc.meta['headers'])}  ")
            elif doc.language == "license":
                if doc.meta.get("header", ""):
                    content.append(f"*Header:* {doc.meta['header']}  ")
            elif doc.language == "dockerfile":
                if doc.meta.get("image", ""):
                    content.append(f"*Image:* {doc.meta['image']}  ")
                if doc.meta.get("workdir", ""):
                    content.append(f"*Workdir:* {doc.meta['workdir']}  ")
                if doc.meta.get("entrypoint", ""):
                    content.append(f"*Entrypoint:* {doc.meta['entrypoint']}  ")
                if doc.meta.get("cmd", ""):
                    content.append(f"*CMD:* {doc.meta['cmd']}  ")
                if doc.meta.get("env", {}):
                    env_str = ', '.join([f"{k}={v}" for k, v in doc.meta['env'].items()])
                    content.append(f"*ENV:* {env_str}  ")            
            
            content.append("")

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        
        self.logger.info(f"Wrote markdown output to {output_path}")


def tree_to_list(tree: dict, path: str = "") -> List[dict]:
    """Convert tree to list of paths with types"""
    result = []
    for name, subtree in tree.items():
        current_path = f"{path}/{name}" if path else name
        if subtree is None:
            result.append({"path": current_path, "type": "file"})
        else:
            dir_entry = {
                "path": current_path, 
                "type": "directory",
                "files": tree_to_list(subtree, current_path)
            }
            result.append(dir_entry)
    return result


class JsonWriter:
    def __init__(self, logger:Logger):
        self.logger = logger
    """Writes output in JSON format"""
    
    def write(self, repo_path: str, documents: List[Document], output_path: str,
              git_analyzer: Optional[GitAnalyzer] = None, commits_limit: int = 20):
        """Generate JSON output"""
        tree = build_folder_structure(documents)
        log_tree(self.logger, tree)
        structure = tree_to_list(tree)
        
        output = {
            "repo": {
                "name": Path(repo_path).absolute().name,
                "path": str(Path(repo_path).absolute()),
                "generated_at": datetime.now().isoformat(),
                "files_processed": len(documents)
            },
            "structure": structure,
            "files": []
        }
        
        # Add Git History
        if git_analyzer and git_analyzer.is_git_repo:
            git_data = {
                "summary": git_analyzer.get_summary(),
                "branches": [],
                "recent_commits": [],
                "contributors": []
            }
            
            # Branches
            branches = git_analyzer.get_branches()
            for branch in branches[:10]:
                git_data["branches"].append({
                    "name": branch.name,
                    "is_current": branch.is_current,
                    "last_commit": branch.last_commit,
                    "last_commit_date": branch.last_commit_date.isoformat()
                })
            
            # Commits
            commits = git_analyzer.get_commits(limit=commits_limit)
            for commit in commits:
                git_data["recent_commits"].append({
                    "hash": commit.hash,
                    "author": commit.author,
                    "email": commit.email,
                    "date": commit.date.isoformat(),
                    "message": commit.message,
                    "files_changed": commit.files_changed,
                    "insertions": commit.insertions,
                    "deletions": commit.deletions
                })
            
            # Contributors
            contributors = git_analyzer.get_contributors()
            for contrib in contributors[:10]:
                git_data["contributors"].append({
                    "name": contrib.name,
                    "email": contrib.email,
                    "commits": contrib.commits,
                    "insertions": contrib.insertions,
                    "deletions": contrib.deletions
                })
            
            output["git_history"] = git_data
        
        for doc in documents:
            file_info = {
                "path": doc.path,
                "language": doc.language,
                "size_bytes": doc.size_bytes,
                "lines": doc.lines,
                "metadata": {}
            }
            
            if doc.language == "python":
                file_info["metadata"]["functions"] = doc.meta.get("functions", [])
                file_info["metadata"]["classes"] = doc.meta.get("classes", [])
            elif doc.language == "markdown":
                file_info["metadata"]["headers"] = doc.meta.get("headers", [])
            elif doc.language == "license":
                file_info["metadata"]["header"] = doc.meta.get("header", "")
            elif doc.language == "dockerfile":
                file_info["metadata"]["image"] = doc.meta.get("image", "")
                file_info["metadata"]["workdir"] = doc.meta.get("workdir", "")
                file_info["metadata"]["entrypoint"] = doc.meta.get("entrypoint", "")
                file_info["metadata"]["cmd"] = doc.meta.get("cmd", "")
                file_info["metadata"]["env"] = doc.meta.get("env", "")
            
            output["files"].append(file_info)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Wrote JSON output to {output_path}")


def tree_to_xml(parent: ET.Element, tree: dict, path: str = ""):
    """Convert tree to XML elements"""
    for name, subtree in tree.items():
        current_path = f"{path}/{name}" if path else name
        if subtree is None:
            item = ET.SubElement(parent, "file")
            item.set("path", current_path)
        else:
            item = ET.SubElement(parent, "directory")
            item.set("path", current_path)
            tree_to_xml(item, subtree, current_path)


class XMLWriter:
    """Writes output in XML format"""
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def write(self, repo_path: str, documents: List[Document], output_path: str,
              git_analyzer: Optional[GitAnalyzer] = None, commits_limit: int = 20):
        """Generate XML output"""
        root = ET.Element("repository")
        
        # Add repo info
        repo_info = ET.SubElement(root, "info")
        ET.SubElement(repo_info, "name").text = Path(repo_path).absolute().name
        ET.SubElement(repo_info, "path").text = str(Path(repo_path).absolute())
        ET.SubElement(repo_info, "generated_at").text = datetime.now().isoformat()
        ET.SubElement(repo_info, "files_processed").text = str(len(documents))
        
        # Add Git History
        if git_analyzer and git_analyzer.is_git_repo:
            git_elem = ET.SubElement(root, "git_history")
            
            # Summary
            summary = git_analyzer.get_summary()
            summary_elem = ET.SubElement(git_elem, "summary")
            ET.SubElement(summary_elem, "current_branch").text = summary.get('current_branch', 'N/A')
            ET.SubElement(summary_elem, "total_commits").text = str(summary.get('total_commits', 0))
            ET.SubElement(summary_elem, "total_contributors").text = str(summary.get('total_contributors', 0))
            if summary.get('first_commit_date'):
                ET.SubElement(summary_elem, "first_commit_date").text = summary['first_commit_date']
            if summary.get('last_commit_date'):
                ET.SubElement(summary_elem, "last_commit_date").text = summary['last_commit_date']
            
            # Branches
            branches = git_analyzer.get_branches()
            if branches:
                branches_elem = ET.SubElement(git_elem, "branches")
                for branch in branches[:10]:
                    branch_elem = ET.SubElement(branches_elem, "branch")
                    branch_elem.set("current", str(branch.is_current).lower())
                    ET.SubElement(branch_elem, "name").text = branch.name
                    ET.SubElement(branch_elem, "last_commit").text = branch.last_commit
                    ET.SubElement(branch_elem, "last_commit_date").text = branch.last_commit_date.isoformat()
            
            # Commits
            commits = git_analyzer.get_commits(limit=commits_limit)
            if commits:
                commits_elem = ET.SubElement(git_elem, "recent_commits")
                for commit in commits:
                    commit_elem = ET.SubElement(commits_elem, "commit")
                    ET.SubElement(commit_elem, "hash").text = commit.hash
                    ET.SubElement(commit_elem, "author").text = commit.author
                    ET.SubElement(commit_elem, "email").text = commit.email
                    ET.SubElement(commit_elem, "date").text = commit.date.isoformat()
                    ET.SubElement(commit_elem, "message").text = commit.message
                    ET.SubElement(commit_elem, "files_changed").text = str(commit.files_changed)
                    ET.SubElement(commit_elem, "insertions").text = str(commit.insertions)
                    ET.SubElement(commit_elem, "deletions").text = str(commit.deletions)
            
            # Contributors
            contributors = git_analyzer.get_contributors()
            if contributors:
                contributors_elem = ET.SubElement(git_elem, "contributors")
                for contrib in contributors[:10]:
                    contrib_elem = ET.SubElement(contributors_elem, "contributor")
                    ET.SubElement(contrib_elem, "name").text = contrib.name
                    ET.SubElement(contrib_elem, "email").text = contrib.email
                    ET.SubElement(contrib_elem, "commits").text = str(contrib.commits)
                    ET.SubElement(contrib_elem, "insertions").text = str(contrib.insertions)
                    ET.SubElement(contrib_elem, "deletions").text = str(contrib.deletions)
        
        # Add folder structure
        structure = ET.SubElement(root, "structure")
        tree = build_folder_structure(documents)
        log_tree(self.logger, tree)
        tree_to_xml(structure, tree)
        
        # Add files
        files_elem = ET.SubElement(root, "files")
        
        for doc in documents:
            file_elem = ET.SubElement(files_elem, "file")
            ET.SubElement(file_elem, "path").text = doc.path
            ET.SubElement(file_elem, "language").text = doc.language
            ET.SubElement(file_elem, "size_bytes").text = str(doc.size_bytes)
            ET.SubElement(file_elem, "lines").text = str(doc.lines)
            
            # Add metadata
            metadata = ET.SubElement(file_elem, "metadata")
            
            if doc.language == "python":
                if doc.meta.get("functions"):
                    funcs = ET.SubElement(metadata, "functions")
                    for func in doc.meta["functions"]:
                        ET.SubElement(funcs, "function").text = func
                if doc.meta.get("classes"):
                    classes = ET.SubElement(metadata, "classes")
                    for cls in doc.meta["classes"]:
                        ET.SubElement(classes, "class").text = cls
            elif doc.language == "markdown":
                if doc.meta.get("headers"):
                    headers = ET.SubElement(metadata, "headers")
                    for header in doc.meta["headers"]:
                        ET.SubElement(headers, "header").text = header
            elif doc.language == "license":
                if doc.meta.get("header"):
                    ET.SubElement(metadata, "header").text = doc.meta["header"]
            elif doc.language == "dockerfile":
                if doc.meta.get("image"):
                    ET.SubElement(metadata, "image").text = doc.meta["image"]
                if doc.meta.get("workdir"):
                    ET.SubElement(metadata, "workdir").text = doc.meta["workdir"]
                if doc.meta.get("entrypoint"):
                    ET.SubElement(metadata, "entrypoint").text = doc.meta["entrypoint"]
                if doc.meta.get("cmd"):
                    ET.SubElement(metadata, "cmd").text = doc.meta["cmd"]
                if doc.meta.get("env"):
                    env_elem = ET.SubElement(metadata, "env")
                    for key, value in doc.meta["env"].items():
                        var = ET.SubElement(env_elem, "variable")
                        var.set("name", key)
                        var.text = value
        
        # Pretty print XML
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")

        # Cut first line (xml version)
        xml_str = '\n'.join(xml_str.split('\n')[1:])
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(xml_str)
        
        self.logger.info(f"Wrote XML output to {output_path}")


class TOONWriter:
    """Writes output in TOON (Token-Oriented Object Notation) format"""
    def __init__(self, logger: Logger):
        self.logger = logger
    
    def _escape_value(self, value: Any) -> str:
        """Escape a value for TOON format"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        # Convert to string and escape if needed
        s = str(value)
        # If string contains comma, newline, or leading/trailing whitespace, quote it
        if ',' in s or '\n' in s or s != s.strip() or '"' in s:
            # Escape double quotes
            s = s.replace('"', '""')
            return f'"{s}"'
        return s
    
    def _format_array(self, arr: List[Any], indent: int = 0) -> List[str]:
        """Format an array in TOON style"""
        lines = []
        if not arr:
            return [f"[0]: "]
        
        # Check if all items are uniform objects (dicts with same keys)
        if all(isinstance(item, dict) for item in arr):
            # Check if they have the same keys
            first_keys = set(arr[0].keys()) if arr else set()
            if all(set(item.keys()) == first_keys for item in arr):
                # Tabular format
                keys = list(arr[0].keys())
                header = f"[{len(arr)}]{{{','.join(keys)}}}:"
                lines.append(header)
                for item in arr:
                    values = [self._escape_value(item.get(k)) for k in keys]
                    lines.append("  " + ",".join(values))
                return lines
        
        # Non-uniform array or simple values
        if all(not isinstance(item, (dict, list)) for item in arr):
            # Simple array of primitives
            values = [self._escape_value(v) for v in arr]
            return [f"[{len(arr)}]: " + ",".join(values)]
        
        # Mixed or nested array - use line-by-line format
        lines.append(f"[{len(arr)}]:")
        for item in arr:
            lines.extend(self._format_value(item, indent + 1))
        return lines
    
    def _format_value(self, value: Any, indent: int = 0) -> List[str]:
        """Format a value recursively"""
        prefix = "  " * indent
        
        if isinstance(value, dict):
            lines = []
            for key, val in value.items():
                if isinstance(val, list):
                    array_lines = self._format_array(val, indent)
                    lines.append(f"{prefix}{key}{array_lines[0]}")
                    lines.extend([f"{prefix}{line}" for line in array_lines[1:]])
                elif isinstance(val, dict):
                    lines.append(f"{prefix}{key}:")
                    lines.extend(self._format_value(val, indent + 1))
                else:
                    lines.append(f"{prefix}{key}: {self._escape_value(val)}")
            return lines
        elif isinstance(value, list):
            return self._format_array(value, indent)
        else:
            return [f"{prefix}{self._escape_value(value)}"]
    
    def write(self, repo_path: str, documents: List[Document], output_path: str,
              git_analyzer: Optional[GitAnalyzer] = None, commits_limit: int = 20):
        """Generate TOON output"""
        content = []
        
        # Build the data structure
        tree = build_folder_structure(documents)
        log_tree(self.logger, tree)
        structure = tree_to_list(tree)
        
        output = {
            "repo": {
                "name": Path(repo_path).absolute().name,
                "path": str(Path(repo_path).absolute()),
                "generated_at": datetime.now().isoformat(),
                "files_processed": len(documents)
            },
            "structure": structure,
            "files": []
        }
        
        # Add Git History
        if git_analyzer and git_analyzer.is_git_repo:
            git_data = {
                "summary": git_analyzer.get_summary(),
                "branches": [],
                "recent_commits": [],
                "contributors": []
            }
            
            # Branches
            branches = git_analyzer.get_branches()
            for branch in branches[:10]:
                git_data["branches"].append({
                    "name": branch.name,
                    "is_current": branch.is_current,
                    "last_commit": branch.last_commit,
                    "last_commit_date": branch.last_commit_date.isoformat()
                })
            
            # Commits
            commits = git_analyzer.get_commits(limit=commits_limit)
            for commit in commits:
                git_data["recent_commits"].append({
                    "hash": commit.hash,
                    "author": commit.author,
                    "email": commit.email,
                    "date": commit.date.isoformat(),
                    "message": commit.message,
                    "files_changed": commit.files_changed,
                    "insertions": commit.insertions,
                    "deletions": commit.deletions
                })
            
            # Contributors
            contributors = git_analyzer.get_contributors()
            for contrib in contributors[:10]:
                git_data["contributors"].append({
                    "name": contrib.name,
                    "email": contrib.email,
                    "commits": contrib.commits,
                    "insertions": contrib.insertions,
                    "deletions": contrib.deletions
                })
            
            output["git_history"] = git_data
        
        # Add files
        for doc in documents:
            file_info = {
                "path": doc.path,
                "language": doc.language,
                "size_bytes": doc.size_bytes,
                "lines": doc.lines,
                "metadata": {}
            }
            
            if doc.language == "python":
                file_info["metadata"]["functions"] = doc.meta.get("functions", [])
                file_info["metadata"]["classes"] = doc.meta.get("classes", [])
            elif doc.language == "markdown":
                file_info["metadata"]["headers"] = doc.meta.get("headers", [])
            elif doc.language == "license":
                file_info["metadata"]["header"] = doc.meta.get("header", "")
            elif doc.language == "dockerfile":
                file_info["metadata"]["image"] = doc.meta.get("image", "")
                file_info["metadata"]["workdir"] = doc.meta.get("workdir", "")
                file_info["metadata"]["entrypoint"] = doc.meta.get("entrypoint", "")
                file_info["metadata"]["cmd"] = doc.meta.get("cmd", "")
                file_info["metadata"]["env"] = doc.meta.get("env", "")
            
            output["files"].append(file_info)
        
        # Convert to TOON format
        toon_lines = self._format_value(output, 0)
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(toon_lines))
        
        self.logger.info(f"Wrote TOON output to {output_path}")
