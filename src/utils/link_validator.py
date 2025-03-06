from pathlib import Path
from typing import List, Set
import re
import urllib.parse
import httpx
from dataclasses import dataclass

@dataclass
class LinkIssue:
    """Represents an issue with a link in the documentation."""
    link: str
    line_number: int
    message: str
    severity: str  # 'error' or 'warning'

class LinkValidator:
    """Validates internal and external links in documentation."""
    
    def __init__(self, repo_path: Path, debug: bool = False):
        self.repo_path = repo_path
        self.checked_urls: Set[str] = set()
        self.issues: List[LinkIssue] = []
        self.debug = debug
    
    async def validate_document(self, content: str, base_path: Path) -> List[LinkIssue]:
        """Validate all links in a markdown document."""
        self.issues = []
        lines = content.split('\n')
        
        # Find all markdown links [text](url)
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        
        for i, line in enumerate(lines, 1):
            for match in re.finditer(link_pattern, line):
                link_text, url = match.groups()
                await self._validate_link(url, i, base_path)
        
        # Find all badge links
        badge_pattern = r'!\[([^\]]+)\]\(([^)]+)\)'
        for i, line in enumerate(lines, 1):
            for match in re.finditer(badge_pattern, line):
                badge_text, url = match.groups()
                await self._validate_link(url, i, base_path)
        
        return self.issues
    
    async def _validate_link(self, url: str, line_number: int, base_path: Path) -> None:
        """Validate a single link."""
        parsed = urllib.parse.urlparse(url)
        
        # Handle internal links
        if not parsed.scheme and not parsed.netloc:
            self._validate_internal_link(url, line_number, base_path)
            return
        
        # Handle external links
        if url not in self.checked_urls:
            await self._validate_external_link(url, line_number)
            self.checked_urls.add(url)
    
    def _validate_internal_link(self, url: str, line_number: int, base_path: Path) -> None:
        """Validate internal file or anchor links."""
        # Remove anchor part for file validation
        file_part = url.split('#')[0]
        
        if not file_part:
            # Anchor-only link, skip file validation
            return
        
        # Handle relative paths
        target_path = (base_path / file_part).resolve()
        
        try:
            relative_to_repo = target_path.relative_to(self.repo_path)
        except ValueError:
            self.issues.append(LinkIssue(
                url,
                line_number,
                "Link points outside repository",
                "error"
            ))
            return
        
        if not target_path.exists():
            self.issues.append(LinkIssue(
                url,
                line_number,
                "Referenced file does not exist",
                "error"
            ))
    
    async def _validate_external_link(self, url: str, line_number: int) -> None:
        """Validate external URLs."""
        try:
            # Create a client with SSL verification disabled
            async with httpx.AsyncClient(verify=False) as client:
                response = await client.head(
                    url,
                    follow_redirects=True,
                    timeout=5.0
                )
                
                if response.status_code >= 400:
                    self.issues.append(LinkIssue(
                        url,
                        line_number,
                        f"Broken link (HTTP {response.status_code})",
                        "error"
                    ))
                elif response.status_code >= 300:
                    self.issues.append(LinkIssue(
                        url,
                        line_number,
                        f"Redirected link (HTTP {response.status_code})",
                        "warning"
                    ))
                    
        except httpx.TimeoutException:
            self.issues.append(LinkIssue(
                url,
                line_number,
                "Link timeout",
                "warning"
            ))
        except Exception as e:
            # Log the error but don't treat SSL errors as link validation failures
            if "SSL" in str(e) or "certificate" in str(e).lower():
                if self.debug:
                    print(f"SSL verification error for {url}: {e}")
            else:
                self.issues.append(LinkIssue(
                    url,
                    line_number,
                    f"Link validation failed: {str(e)}",
                    "error"
                )) 