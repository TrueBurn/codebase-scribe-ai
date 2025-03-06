from typing import Dict, Set
import networkx as nx
from pathlib import Path

class MermaidGenerator:
    """Generates Mermaid diagram syntax for architecture visualization."""
    
    def __init__(self, graph: nx.DiGraph):
        self.graph = graph
        
    def generate_class_diagram(self) -> str:
        """Generate a class diagram showing module relationships."""
        content = ["```mermaid", "classDiagram"]
        
        # Add all nodes (modules)
        for node in self.graph.nodes():
            exports = self.graph.nodes[node].get('exports', [])
            if exports:
                content.append(f"class {node} {{")
                for export in exports:
                    content.append(f"    +{export}")
                content.append("}")
            else:
                content.append(f"class {node}")
        
        # Add relationships
        for src, dst in self.graph.edges():
            content.append(f"{src} --> {dst}")
        
        content.append("```\n")
        return "\n".join(content)
    
    def generate_dependency_flowchart(self) -> str:
        """Generate a flowchart showing module dependencies."""
        content = ["```mermaid", "flowchart LR"]
        
        # Add nodes with unique IDs
        for node in self.graph.nodes():
            # Clean node name for Mermaid compatibility
            node_id = node.replace(".", "_")
            content.append(f"    {node_id}[{node}]")
        
        # Add edges
        for src, dst in self.graph.edges():
            # Clean node names
            src_id = src.replace(".", "_")
            dst_id = dst.replace(".", "_")
            content.append(f"    {src_id} --> {dst_id}")
        
        content.append("```\n")
        return "\n".join(content)
    
    def generate_package_diagram(self) -> str:
        """Generate a package diagram showing directory-level dependencies."""
        # Group nodes by directory
        packages: Dict[str, Set[str]] = {}
        for node in self.graph.nodes():
            path = Path(node)
            pkg = str(path.parent) if path.parent.name else "root"
            if pkg not in packages:
                packages[pkg] = set()
            packages[pkg].add(node)
        
        content = ["```mermaid", "flowchart TB"]
        
        # Add subgraphs for each package
        for pkg, modules in packages.items():
            pkg_id = pkg.replace(".", "_").replace("/", "_")
            content.append(f"    subgraph {pkg_id}[{pkg}]")
            for module in modules:
                mod_id = module.replace(".", "_")
                content.append(f"        {mod_id}[{Path(module).name}]")
            content.append("    end")
        
        # Add edges
        for src, dst in self.graph.edges():
            src_id = src.replace(".", "_")
            dst_id = dst.replace(".", "_")
            content.append(f"    {src_id} --> {dst_id}")
        
        content.append("```\n")
        return "\n".join(content) 