from typing import Dict, Any, List, Optional
import json
import logging

class MessageManager:
    """Manages message formatting for different LLM providers."""
    
    @staticmethod
    def create_system_user_messages(system_content: str, user_content: str) -> List[Dict[str, str]]:
        """Create standard system and user messages."""
        return [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content}
        ]
    
    @staticmethod
    def get_project_overview_messages(project_structure: str, tech_report: str, template_content: str) -> List[Dict[str, str]]:
        """Get standardized messages for project overview generation."""
        system_content = f"""Project Structure:
{project_structure}

Detected Technologies:
{tech_report}

Analyze in English and ensure all responses are in English.
Use proper markdown formatting:
- Ensure headers follow proper hierarchy (H1 → H2 → H3)
- Use consistent list indentation (multiples of 2 spaces)
- Add blank lines before headers"""
        
        return MessageManager.create_system_user_messages(system_content, template_content)
    
    @staticmethod
    def get_component_relationship_messages(project_structure: str, tech_report: str) -> List[Dict[str, str]]:
        """Get standardized messages for component relationship analysis."""
        system_content = f"""Project Structure:
{project_structure}

Detected Technologies:
{tech_report}

IMPORTANT INSTRUCTION: ONLY discuss technologies and patterns that are explicitly 
evidenced in the Detected Technologies section above. DO NOT assume or infer the
presence of any framework, library, or architecture that is not directly observable
in the codebase. If the technology stack is unclear, acknowledge the limitations
rather than making assumptions.

Analyze in English and ensure all responses are in English.
Use proper markdown formatting:
- Ensure headers follow proper hierarchy (H1 → H2 → H3)
- Use consistent list indentation (multiples of 2 spaces)
- Add blank lines before headers"""
        
        user_content = """Analyze how the major components in this project interact with each other.

Include:
- Main data/control flow
- Key dependencies
- Important interfaces
- Notable design patterns

Focus on high-level architectural relationships that are ACTUALLY present in the code,
not what you think should be there based on common patterns."""
        
        return MessageManager.create_system_user_messages(system_content, user_content)
    
    @staticmethod
    def get_file_summary_messages(prompt: str) -> List[Dict[str, str]]:
        """Get standardized messages for file summary generation."""
        system_content = """You are a code documentation expert. Analyze the provided code file and create a clear, 
concise summary that explains:
1. The purpose and functionality of the file
2. Key components, classes, or functions
3. Important algorithms or patterns used
4. How this file relates to the overall project
5. Any notable dependencies or imports
6. Use proper markdown formatting with consistent indentation"""
        
        return MessageManager.create_system_user_messages(system_content, prompt)
    
    @staticmethod
    def get_architecture_content_messages(project_structure: str, key_components: str, tech_report: str) -> List[Dict[str, str]]:
        """Get standardized messages for architecture documentation generation."""
        system_content = """You are a technical documentation expert. Create comprehensive architecture documentation for this project.
        
Include the following sections:
1. Overview - A high-level description of the project architecture
2. Project Structure - Include the provided structure as a code block
3. Component Diagram - Create a mermaid flowchart diagram showing the main components and their relationships
4. Data Flow - Describe how data flows through the system
5. Key Technologies - List and explain the technologies used
6. Design Patterns - Identify any design patterns used in the project

Use proper markdown formatting with appropriate headers and code blocks.
For the Component Diagram, use mermaid.js flowchart syntax like this:
```mermaid
flowchart TD
    A[Component A] --> B[Component B]
    A --> C[Component C]
    B --> D[Component D]
    C --> D
```

Analyze the project structure to identify the main components and their relationships."""

        user_content = f"""Based on the following project information, create detailed architecture documentation.

Project Structure:
```
{project_structure}
```

Key Components:
{key_components}

Technologies:
{tech_report}

Please include a mermaid flowchart diagram showing the relationships between key components."""

        return MessageManager.create_system_user_messages(system_content, user_content)
    
    @staticmethod
    def get_enhance_documentation_messages(existing_content: str, project_structure: str, 
                                          key_components: str, tech_report: str, doc_type: str) -> List[Dict[str, str]]:
        """Get standardized messages for enhancing existing documentation."""
        system_content = f"""You are a technical documentation expert specializing in {doc_type} files.
        
Project Structure:
{project_structure}

Key Components:
{key_components}

Detected Technologies:
{tech_report}

Your task is to enhance the existing {doc_type} file by:
1. Preserving valuable information from the existing content
2. Reorganizing the document structure for better clarity and flow
3. Removing outdated, redundant, or incorrect information
4. Adding missing information based on the repository analysis
5. Ensuring proper markdown formatting with consistent header hierarchy
6. Maintaining code snippets and examples, updating them only if incorrect
7. Maintaining the original tone and style where appropriate

Return a completely restructured document that represents the best possible documentation for this codebase.
"""
        
        user_content = f"""Here is the existing {doc_type} content:

{existing_content}

Please enhance this document by intelligently combining the existing content with new insights from the repository analysis.
Create the best possible documentation that accurately represents the codebase.
"""
        
        return MessageManager.create_system_user_messages(system_content, user_content)
    
    @staticmethod
    def get_usage_guide_messages(project_structure: str, tech_report: str) -> List[Dict[str, str]]:
        """Get standardized messages for usage guide generation."""
        system_content = """You are a technical documentation expert. Create clear usage instructions based on the project structure."""
        
        user_content = f"""Based on the project structure and dependencies, generate a usage guide.
        
Project Structure:
{project_structure}

Dependencies:
{tech_report}

Please provide clear instructions for:
1. Basic usage examples
2. Common operations
3. Configuration options
4. Troubleshooting tips

Use proper markdown formatting with clear section headers."""
        
        return MessageManager.create_system_user_messages(system_content, user_content)
    
    @staticmethod
    def get_contributing_guide_messages(project_structure: str) -> List[Dict[str, str]]:
        """Get standardized messages for contributing guide generation."""
        system_content = """You are a technical documentation expert. Create clear contributing guidelines based on the project structure."""
        
        user_content = f"""Based on the project structure, generate a contributing guide.
        
Project Structure:
{project_structure}

Please provide clear guidelines for:
1. Setting up the development environment
2. Code style and standards
3. Testing procedures
4. Pull request process
5. Issue reporting

Use proper markdown formatting with clear section headers."""
        
        return MessageManager.create_system_user_messages(system_content, user_content)
    
    @staticmethod
    def get_license_info_messages(project_structure: str) -> List[Dict[str, str]]:
        """Get standardized messages for license information generation."""
        system_content = """You are a technical documentation expert. Create clear license information based on the project structure."""
        
        user_content = f"""Based on the project structure, generate license information.
        
Project Structure:
{project_structure}

Please provide:
1. License type (if detectable)
2. Brief explanation of the license
3. Any copyright notices found

If no license information is found, provide a generic statement about licensing.
Use proper markdown formatting."""
        
        return MessageManager.create_system_user_messages(system_content, user_content)
    
    @staticmethod
    def get_file_order_messages(files_info: dict) -> List[Dict[str, str]]:
        """Get standardized messages for file order optimization."""
        system_content = """Determine the optimal order for analyzing files in a codebase.
        Follow these rules:
        1. Configuration files first (e.g., appsettings.json)
        2. Core infrastructure and utilities next
        3. Base classes before implementations
        4. Simpler files before complex ones
        5. Respect dependencies (if A depends on B, process B first)
        6. Always respond in English
        
        IMPORTANT: Return your response as a JSON object with a "file_order" array containing the file paths in the optimal order.
        Example: {"file_order": ["config.json", "utils.py", "main.py"], "reasoning": "Config files first, then utilities, then main application code."}"""
        
        user_content = json.dumps({
            "files": files_info,
            "task": "Analyze these files and return them in optimal processing order"
        }, indent=2)
        
        return MessageManager.create_system_user_messages(system_content, user_content)
    
    @staticmethod
    def check_and_truncate_messages(messages: List[Dict[str, str]], token_counter, model_name: str) -> List[Dict[str, str]]:
        """Check if messages exceed token limit and truncate if needed."""
        will_exceed, token_count = token_counter.will_exceed_limit(messages, model_name)
        
        if not will_exceed:
            return messages
        
        # If we exceed the limit, we need to truncate the user message content
        # System message is usually shorter and more important for context
        truncated_messages = messages.copy()
        
        # First try with the new intelligent reduction method
        for i, message in enumerate(truncated_messages):
            if message["role"] == "user":
                # Use the new intelligent reduction method
                truncated_content = token_counter.handle_oversized_input(
                    message["content"], 
                    target_percentage=0.8
                )
                truncated_messages[i]["content"] = truncated_content
                
                # Check if we're now under the limit
                still_exceeds, new_count = token_counter.will_exceed_limit(truncated_messages, model_name)
                if not still_exceeds:
                    logging.info(f"Intelligently reduced message from {token_count} to {new_count} tokens")
                    return truncated_messages
        
        # If intelligent reduction wasn't enough, fall back to simple truncation
        for i, message in enumerate(truncated_messages):
            if message["role"] == "user":
                # Get the effective limit for this message
                # We'll use 90% of the model's limit minus the tokens from other messages
                other_messages = [m for j, m in enumerate(messages) if j != i]
                other_tokens = token_counter.count_message_tokens(other_messages)
                model_limit = token_counter.get_token_limit(model_name)
                effective_limit = int(model_limit * 0.9) - other_tokens
                
                # Truncate the content
                truncated_content = token_counter.truncate_text(message["content"], effective_limit)
                truncated_messages[i]["content"] = truncated_content
                
                logging.warning(f"Forced to truncate message to {effective_limit} tokens")
                break  # Only truncate one message (the user message)
        
        return truncated_messages 