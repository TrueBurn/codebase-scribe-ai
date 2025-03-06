import re
from pathlib import Path
from typing import List
from dataclasses import dataclass

@dataclass
class ValidationIssue:
    """Represents a markdown validation issue."""
    line_number: int
    message: str
    severity: str  # 'error' or 'warning'
    suggestion: str = None

class MarkdownValidator:
    """Validates and fixes common markdown issues."""
    
    def __init__(self, content: str):
        self.content = content
        self.lines = content.split('\n')
        
    def validate(self) -> List[ValidationIssue]:
        """Run all validation checks and return found issues."""
        issues = []
        issues.extend(self._check_headers())
        issues.extend(self._check_link_syntax())
        issues.extend(self._check_code_blocks())
        issues.extend(self._check_list_formatting())
        issues.extend(self._check_mermaid_syntax())
        return issues
    
    def _check_headers(self) -> List[ValidationIssue]:
        """Check for proper header formatting and hierarchy."""
        issues = []
        prev_level = 0
        
        for i, line in enumerate(self.content.split('\n')):
            # Skip lines that aren't headers
            if not line.strip().startswith('#'):
                continue
            
            # Check if this is a header line
            header_match = re.match(r'^(#+)\s', line)
            if not header_match:
                # This is a line starting with # but not formatted as a header
                issues.append(ValidationIssue(
                    line_number=i+1,
                    message="Header missing space after # characters",
                    severity="error",
                    suggestion=f"Add a space after the # characters: {line.replace('#', '# ', 1)}"
                ))
                continue
            
            # Get header level
            level = len(header_match.group(1))
            
            # Check header hierarchy
            if level > prev_level + 1 and prev_level > 0:
                issues.append(ValidationIssue(
                    line_number=i+1,
                    message=f"Header level jumped from {prev_level} to {level}",
                    severity="warning",
                    suggestion=f"Consider using a level {prev_level + 1} header instead"
                ))
            
            prev_level = level
        
        return issues
    
    def _check_link_syntax(self) -> List[ValidationIssue]:
        """Check for proper link formatting."""
        issues = []
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^\)]+)\)')
        
        for i, line in enumerate(self.lines):
            # Find all links in the line
            for match in link_pattern.finditer(line):
                text, url = match.groups()
                
                # Check for empty link text
                if not text.strip():
                    issues.append(ValidationIssue(
                        i + 1,
                        "Link has empty text",
                        'error',
                        "Add descriptive link text"
                    ))
                
                # Check for broken relative links
                if not url.startswith(('http', 'https', '#', 'mailto:')):
                    path = Path(url)
                    if not path.exists():
                        issues.append(ValidationIssue(
                            i + 1,
                            f"Relative link to '{url}' might be broken",
                            'warning'
                        ))
        
        return issues
    
    def _check_code_blocks(self) -> List[ValidationIssue]:
        """Check code block formatting."""
        issues = []
        in_code_block = False
        
        for i, line in enumerate(self.lines):
            if line.startswith('```'):
                if in_code_block:
                    in_code_block = False
                else:
                    in_code_block = True
                    # Check if language is specified
                    if len(line.strip()) == 3:
                        issues.append(ValidationIssue(
                            i + 1,
                            "Code block language not specified",
                            'warning',
                            "Specify language for syntax highlighting"
                        ))
        
        if in_code_block:
            issues.append(ValidationIssue(
                len(self.lines),
                "Unclosed code block",
                'error',
                "Add closing ```"
            ))
        
        return issues
    
    def _check_list_formatting(self) -> List[ValidationIssue]:
        """Check list formatting and indentation."""
        issues = []
        
        for i, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped.startswith(('- ', '* ', '+ ')):
                # Check list item indentation
                indent = len(line) - len(line.lstrip())
                if indent % 2 != 0:
                    issues.append(ValidationIssue(
                        i + 1,
                        "List item indentation should be multiple of 2 spaces",
                        'warning'
                    ))
                
                # Check for consistent list marker style
                if i > 0:
                    prev_line = self.lines[i-1].strip()
                    if prev_line.startswith(('- ', '* ', '+ ')):
                        prev_marker = prev_line[0]
                        curr_marker = stripped[0]
                        if prev_marker != curr_marker:
                            issues.append(ValidationIssue(
                                i + 1,
                                "Inconsistent list marker style",
                                'warning',
                                f"Use '{prev_marker}' consistently"
                            ))
        
        return issues
    
    def _check_mermaid_syntax(self) -> List[ValidationIssue]:
        """Check Mermaid diagram syntax."""
        issues = []
        in_mermaid = False
        
        for i, line in enumerate(self.lines):
            if line.strip() == '```mermaid':
                in_mermaid = True
                # Check if next line defines diagram type
                if i + 1 < len(self.lines):
                    next_line = self.lines[i + 1].strip()
                    if not any(next_line.startswith(t) for t in ['graph', 'flowchart', 'sequenceDiagram', 'classDiagram']):
                        issues.append(ValidationIssue(
                            i + 2,
                            "Mermaid diagram type not specified",
                            'error',
                            "Add diagram type (e.g., 'flowchart LR')"
                        ))
            elif line.strip() == '```':
                in_mermaid = False
        
        return issues
    
    def fix_common_issues(self) -> str:
        """Attempt to fix common markdown issues."""
        fixed_lines = self.lines.copy()
        
        # Fix header spacing (add space after # characters)
        for i, line in enumerate(fixed_lines):
            if line.strip().startswith('#'):
                # Fix missing space after # in headers
                header_match = re.match(r'^(#+)([^\s])', line)
                if header_match:
                    prefix = header_match.group(1)
                    rest = header_match.group(2) + line[len(prefix) + 1:]
                    fixed_lines[i] = f"{prefix} {rest}"
                
                # Add blank line before headers (except at the start of the document)
                if i > 0 and fixed_lines[i-1].strip():
                    fixed_lines.insert(i, '')
                    i += 1
        
        # Fix list marker consistency and indentation
        list_marker = None
        list_indent_base = None
        in_list = False
        
        for i, line in enumerate(fixed_lines):
            stripped = line.strip()
            
            # Check for list items
            list_match = re.match(r'^(\s*)([*+-])\s', line)
            if list_match:
                indent = list_match.group(1)
                marker = list_match.group(2)
                
                # Set consistent list marker
                if not in_list:
                    list_marker = marker
                    list_indent_base = len(indent)
                    in_list = True
                else:
                    # Fix marker consistency
                    if marker != list_marker:
                        fixed_lines[i] = line.replace(marker, list_marker, 1)
                    
                    # Fix indentation to be multiple of 2 spaces
                    current_indent = len(indent)
                    if current_indent > list_indent_base:
                        desired_indent = list_indent_base + (((current_indent - list_indent_base) + 1) // 2) * 2
                        if current_indent != desired_indent:
                            fixed_lines[i] = ' ' * desired_indent + line.lstrip()
            elif stripped == '':
                # Empty line might end a list
                if i+1 < len(fixed_lines) and not re.match(r'^\s*[*+-]\s', fixed_lines[i+1]):
                    in_list = False
            else:
                # Non-list item ends the list context
                in_list = False
        
        return '\n'.join(fixed_lines) 