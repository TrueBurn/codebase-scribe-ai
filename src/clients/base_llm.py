from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

class BaseLLMClient(ABC):
    """Base abstract class for LLM clients."""
    
    @abstractmethod
    async def initialize(self):
        """Initialize the client."""
        pass
    
    @abstractmethod
    async def generate_summary(self, prompt: str) -> Optional[str]:
        """Generate a summary for a file's content."""
        pass
    
    @abstractmethod
    async def generate_project_overview(self, file_manifest: dict) -> str:
        """Generate project overview based on file manifest."""
        pass

    
    @abstractmethod
    async def generate_usage_guide(self, file_manifest: dict) -> str:
        """Generate usage guide based on project structure."""
        pass
    
    @abstractmethod
    async def generate_contributing_guide(self, file_manifest: dict) -> str:
        """Generate contributing guide based on project structure."""
        pass
    
    @abstractmethod
    async def generate_license_info(self, file_manifest: dict) -> str:
        """Generate license information based on project structure."""
        pass
    
    @abstractmethod
    async def generate_architecture_content(self, file_manifest: dict, analyzer) -> str:
        """Generate architecture documentation content."""
        pass
    
    @abstractmethod
    async def generate_component_relationships(self, file_manifest: dict) -> str:
        """Generate description of how components interact."""
        pass
    
    @abstractmethod
    async def enhance_documentation(self, existing_content: str, file_manifest: dict, doc_type: str) -> str:
        """Enhance existing documentation with new insights."""
        pass
    
    @abstractmethod
    def set_project_structure(self, structure: str):
        """Set the project structure for use in prompts."""
        pass
    
    @abstractmethod
    async def get_file_order(self, project_files: dict) -> list[str]:
        """Determine optimal file processing order."""
        pass 