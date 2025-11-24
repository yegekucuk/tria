#!/usr/bin/env python3
"""
tria - Turn repositories into AI-friendly summaries
Author: @yegekucuk
"""
import logging
from pathlib import Path
import argparse

from src.chunker import SimpleChunker
from src.readers import RepoReader
from src.writers import JsonWriter, MarkdownWriter, XMLWriter, TOONWriter
from src.git_analyzer import GitAnalyzer


def main():
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(
        description="tria - Turn Python repositories into AI-friendly format.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tria .
  tria ./my-repo -f md -o repo_summary.md
  tria . --exclude 'tests' --format json
  tria /path/to/repo --verbose --chunk-size 100
  tria . --git-history --format json -o repo.json
        """
    )
    
    parser.add_argument('path', help='Path to repository')
    parser.add_argument('-f', '--format', choices=['toon', 'md', 'json', 'xml'], default='toon',
                       help='Output format (default: toon)')
    parser.add_argument('-o', '--output', 
                       help='Output file path (default: ./tria_output.[toon|md|json|xml])')
    parser.add_argument('--exclude', action='append', default=[],
                       help='Exclude path pattern (can be repeated)')
    parser.add_argument('--no-gitignore', action='store_false', dest='gitignore',
                       help='Do not use .gitignore to exclude files (gitignore is used by default)')
    parser.add_argument('--git-history', action='store_true',
                       help='Include git history')
    parser.add_argument('--git-commits', type=int, default=20,
                       help='Number of recent commits to include (default: 20)')
    parser.add_argument('--chunk-size', type=int, default=50,
                       help='Lines per chunk (default: 50)')
    parser.add_argument('--max-files', type=int, default=1000,
                       help='Max files to process (default: 1000)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Do everything except writing output')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose logging')
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate path
    repo_path = Path(args.path)
    if not repo_path.exists():
        logger.error(f"Path does not exist: {args.path}")
        return 1
    
    # Set default output path
    project_name = repo_path.absolute().name
    if not args.output:
        ext = args.format
        args.output = f"./{project_name}_summary.{ext}"
    
    logger.info(f"Processing repository: {repo_path}")
    logger.info(f"Output format: {args.format}")
    
    # Initialize git analyzer only if user requested git history
    git_analyzer = None
    if args.git_history:
        git_analyzer = GitAnalyzer(str(repo_path), logger)
        if not git_analyzer.is_git_repo:
            logger.warning("Not a git repository - skipping git history")
            git_analyzer = None
        else:
            logger.info("Git repository detected and git history will be included")
    else:
        logger.info("Git history not requested; skipping git analysis")
    
    # Read files
    reader = RepoReader(path=str(repo_path), logger=logger, exclude_patterns=args.exclude, use_gitignore=args.gitignore)
    documents = reader.read_files(max_files=args.max_files)
    
    if not documents:
        logger.warning("No files found to process")
        return 1
    
    # Initialize components
    chunker = SimpleChunker(chunk_size=args.chunk_size)
    
    # Process chunks
    total_chunks = 0
    for doc in documents:
        chunks = chunker.chunk_document(doc)
        total_chunks += len(chunks)
    
    logger.info(f"Created {total_chunks} chunks from {len(documents)} documents")
    
    # Write output
    if not args.dry_run:
        match args.format:
            case "xml":
                writer = XMLWriter(logger)
            case "json":
                writer = JsonWriter(logger)
            case "md":
                writer = MarkdownWriter(logger)
            case _:
                writer = TOONWriter(logger)
        writer.write(str(repo_path), documents, args.output, git_analyzer, args.git_commits)
        logger.info(f"✓ Output written to: {args.output}")
    else:
        logger.info("Dry run - no output written")
    
    return 0

if __name__ == '__main__':
    exit(main())
