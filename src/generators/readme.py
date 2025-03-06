from pathlib import Path
from ..utils.markdown_validator import MarkdownValidator
from ..utils.readability import ReadabilityScorer
from ..utils.link_validator import LinkValidator
from ..clients.base_llm import BaseLLMClient
from ..analyzers.codebase import CodebaseAnalyzer
import logging
from typing import Optional
import re

async def generate_readme(
    repo_path: Path,
    llm_client: BaseLLMClient,
    file_manifest: dict,
    file_summaries: dict,
    config: dict,
    analyzer: CodebaseAnalyzer,
    output_dir: str,
    existing_readme: Optional[str] = None,
    architecture_file_exists: bool = False
) -> str:
    """Generate README content using file summaries."""
    try:
        # Use the analyzer's method to get a consistent project name
        project_name = analyzer.derive_project_name(config.get('debug', False))
        logging.info(f"Using project name: {project_name}")
        
        # Check if we should preserve existing content
        preserve_existing = config.get('preserve_existing', True)  # Default to True
        readme_path = repo_path / 'README.md'
        
        if preserve_existing and readme_path.exists():
            try:
                existing_content = readme_path.read_text(encoding='utf-8')
                # Check if it's not just a placeholder or default README
                if len(existing_content.strip().split('\n')) > 5:  # More than 5 lines suggests meaningful content
                    logging.info("Found existing README.md with meaningful content. Will enhance rather than replace.")
                    print("Enhancing existing README.md rather than replacing it.")
                    
                    # Generate project overview for context
                    try:
                        overview = await llm_client.generate_project_overview(file_manifest)
                        logging.info(f"Generated overview length: {len(overview) if overview else 0}")
                    except Exception as e:
                        logging.error(f"Error generating overview for enhancement: {e}")
                        overview = f"{project_name} is a software project."
                    
                    # Enhance existing content
                    enhanced_content = await llm_client.enhance_documentation(
                        existing_content=existing_content,
                        file_manifest=file_manifest,
                        doc_type="README.md"
                    )
                    
                    # Check for leaked instructions in the enhanced content
                    instruction_phrases = [
                        "Your task is to preserve",
                        "Do not remove specific implementation",
                        "Focus on adding missing information",
                        "Maintain the original structure",
                        "Return the enhanced document"
                    ]
                    
                    # Remove any leaked instructions
                    for phrase in instruction_phrases:
                        enhanced_content = enhanced_content.replace(phrase, "")
                    
                    # Add link to ARCHITECTURE.md if it exists and not already mentioned
                    if architecture_file_exists and "ARCHITECTURE.md" not in enhanced_content:
                        architecture_link = "\n\n## Architecture\n\nFor detailed architecture documentation, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).\n"
                        
                        # Find a good place to insert the link
                        if "## Usage" in enhanced_content:
                            enhanced_content = enhanced_content.replace("## Usage", f"{architecture_link}\n## Usage")
                        else:
                            # Append to the end if no good insertion point
                            enhanced_content += architecture_link
                    
                    # Make sure the title uses the correct project name
                    title_match = re.search(r'^# (.+?)(?:\n|$)', enhanced_content)
                    if title_match:
                        old_title = title_match.group(1)
                        if old_title.lower() == "project" or old_title.strip() == "":
                            enhanced_content = enhanced_content.replace(f"# {old_title}", f"# {project_name}")
                    else:
                        # No title found, add one
                        enhanced_content = f"# {project_name}\n\n{enhanced_content}"
                    
                    return enhanced_content
            except Exception as e:
                logging.error(f"Error enhancing existing README: {e}")
                logging.info("Falling back to generating new README")
        
        # Generate new README from scratch
        try:
            # Get a comprehensive project overview
            logging.info("Generating project overview...")
            try:
                overview = await llm_client.generate_project_overview(file_manifest)
                logging.info(f"Generated overview length: {len(overview) if overview else 0}")
            except Exception as e:
                logging.error(f"Error in LLM call for project overview: {e}")
                overview = None
            
            # If overview is empty or failed, try to extract from architecture document
            if not overview and architecture_file_exists:
                logging.info("Attempting to extract overview from ARCHITECTURE.md...")
                arch_path = repo_path / "docs" / "ARCHITECTURE.md"
                if arch_path.exists():
                    try:
                        arch_content = arch_path.read_text(encoding='utf-8')
                        overview_match = re.search(r'## Overview\s+(.+?)(?=##|\Z)', arch_content, re.DOTALL)
                        if overview_match:
                            overview = overview_match.group(1).strip()
                            logging.info(f"Using overview from ARCHITECTURE.md, length: {len(overview)}")
                    except Exception as e:
                        logging.error(f"Error reading ARCHITECTURE.md: {e}")
            
            # If still not available, try to extract from usage section
            if not overview:
                logging.info("Attempting to generate usage guide for overview extraction...")
                try:
                    usage_text = await llm_client.generate_usage_guide(file_manifest)
                    if usage_text and len(usage_text) > 100:
                        # Extract first paragraph as overview
                        first_para = usage_text.split('\n\n')[0]
                        if len(first_para) > 50:
                            overview = first_para
                            logging.info(f"Using first paragraph of usage as overview, length: {len(overview)}")
                except Exception as e:
                    logging.error(f"Error generating usage for overview: {e}")
            
            # If still not available, use a fallback
            if not overview:
                logging.info("Using fallback overview text")
                overview = f"{project_name} is a software project containing {len(file_manifest)} files. Please refer to the documentation for more details."
        except Exception as e:
            logging.error(f"Error in overview generation process: {e}")
            overview = f"{project_name} is a software project containing {len(file_manifest)} files."
        
        try:
            usage = await llm_client.generate_usage_guide(file_manifest)
            if not usage or len(usage) < 50:
                usage = "Please refer to project documentation for usage instructions."
        except Exception as e:
            logging.error(f"Error generating usage guide: {e}")
            usage = "Please refer to project documentation for usage instructions."
        
        try:
            contributing = await llm_client.generate_contributing_guide(file_manifest)
            if not contributing or len(contributing) < 50:
                contributing = "Please refer to project documentation for contribution guidelines."
        except Exception as e:
            logging.error(f"Error generating contributing guide: {e}")
            contributing = "Please refer to project documentation for contribution guidelines."
        
        try:
            license_info = await llm_client.generate_license_info(file_manifest)
            if not license_info or len(license_info) < 20:
                license_info = "Please refer to the LICENSE file for license information."
        except Exception as e:
            logging.error(f"Error generating license info: {e}")
            license_info = "Please refer to the LICENSE file for license information."
        
        # Add architecture link if ARCHITECTURE.md exists
        architecture_section = ""
        if architecture_file_exists:
            architecture_section = "\n## Architecture\n\nFor detailed architecture documentation, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).\n"
        
        # Remove any existing markdown headers from the sections
        overview = _clean_section_headers(overview)
        usage = _clean_section_headers(usage)
        contributing = _clean_section_headers(contributing)
        license_info = _clean_section_headers(license_info)
        
        readme_content = f"""# {project_name}

## Table of Contents
- [Overview](#overview)
{architecture_section and f"- [Architecture](#{_format_anchor_link('Architecture')})" or ""}
- [Usage](#{_format_anchor_link('Usage')})
- [Contributing](#{_format_anchor_link('Contributing')})
- [License](#{_format_anchor_link('License')})

## Overview

{overview}

{architecture_section}

## Usage

{usage}

## Contributing

{contributing}

## License

{license_info}
"""

        # Validate links in the generated content
        content = readme_content
        
        # Validate markdown structure
        md_validator = MarkdownValidator(content)
        markdown_issues = md_validator.validate()
        if markdown_issues:
            logging.warning("Found markdown formatting issues in new README:")
            for issue in markdown_issues:
                logging.warning(f"  - {issue}")
        
        # Validate links
        validator = LinkValidator(repo_path)
        invalid_links = await validator.validate_document(content, repo_path)
        
        if invalid_links:
            logging.warning(f"Found {len(invalid_links)} invalid links in new README")
            for issue in invalid_links:
                logging.warning(f"  - {issue}")
        
        # Check readability
        scorer = ReadabilityScorer()
        score = scorer.analyze_text(content, "README")
        
        if isinstance(score, dict):
            # Extract the overall score from the dictionary
            overall_score = score.get('overall', 0)
            if overall_score > 40:  # Higher score means more complex text
                print("\nWarning: README.md content may be too complex.")
                print("Recommendations:")
                print("- Consider simplifying language for better readability")
                print("- Use simpler words where possible")
        elif score > 40:  # For backward compatibility if score is a number
            print("\nWarning: README.md content may be too complex.")
            print("Recommendations:")
            print("- Consider simplifying language for better readability")
            print("- Use simpler words where possible")
        
        # Apply automatic fixes
        content = md_validator.fix_common_issues()
        
        # Validate again to see if issues were resolved
        fixed_validator = MarkdownValidator(content)
        remaining_issues = fixed_validator.validate()
        if remaining_issues:
            logging.info(f"Fixed some issues. {len(remaining_issues)} issues remain.")
        else:
            logging.info("All markdown issues were automatically fixed!")
        
        return content
    except Exception as e:
        logging.error(f"Error generating README: {e}")
        # Return a minimal valid README instead of an error message
        return f"""# {repo_path.name}

## Overview

This is the README for the {repo_path.name} project.

## Architecture

For detailed architecture documentation, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

---
*This README was automatically generated but encountered errors during processing.*
"""

def _clean_section_headers(content: str) -> str:
    """Remove existing markdown headers from a section to prevent duplicates."""
    if not content:
        return ""
    
    # Remove any lines that start with # at the beginning of the content
    lines = content.split('\n')
    while lines and lines[0].strip().startswith('#'):
        lines.pop(0)
    
    # Join the remaining lines
    return '\n'.join(lines).strip()

def _format_anchor_link(section_name: str) -> str:
    """Format a section name into a proper anchor link by removing special characters."""
    return section_name.lower().replace(' ', '-').replace('.', '').replace('/', '').replace('(', '').replace(')', '') 