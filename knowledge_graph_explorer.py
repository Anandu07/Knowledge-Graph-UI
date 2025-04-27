import streamlit as st
import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd
import re
import json
from pyvis.network import Network
import tempfile
import os
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Knowledge Graph",
    page_icon="🧠",
    layout="wide"
)

# Function to parse Cypher file
def parse_cypher_file(file_path):
    """
    Parse a Cypher script file to extract nodes and relationships
    """
    st.info(f"Parsing Cypher file: {file_path}")
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as file:
        cypher_script = file.read()
    
    # Initialize collections to store data
    knowledge_nodes = {}
    concepts = {}
    learning_paths = {}
    relationships = []
    
    # Extract KnowledgeNode creations
    knowledge_node_pattern = r"CREATE \(n:KnowledgeNode \{\s*id: \"(N\d+)\",\s*title: \"([^\"]+)\",\s*description: \"([^\"]+)\",\s*difficulty: \"([^\"]+)\",\s*estimatedMinutes: (\d+),\s*source_lesson: \"([^\"]*)\",\s*source_title: \"([^\"]*)\"\s*\}\);"
    
    for match in re.finditer(knowledge_node_pattern, cypher_script):
        node_id, title, description, difficulty, minutes, source_lesson, source_title = match.groups()
        knowledge_nodes[node_id] = {
            "id": node_id,
            "title": title,
            "description": description,
            "difficulty": difficulty,
            "estimatedMinutes": int(minutes),
            "source_lesson": source_lesson,
            "source_title": source_title
        }
    
    # Extract Concept creations
    concept_pattern = r"CREATE \(c:Concept \{\s*id: \"(CONCEPT-\d+)\",\s*name: \"([^\"]+)\",\s*description: \"([^\"]+)\",\s*estimatedMinutes: (\d+)\s*\}\);"
    
    for match in re.finditer(concept_pattern, cypher_script):
        concept_id, name, description, minutes = match.groups()
        concepts[concept_id] = {
            "id": concept_id,
            "name": name,
            "description": description,
            "estimatedMinutes": int(minutes),
            "nodes": []  # Will be populated later
        }
    
    # Extract LearningPath creations
    path_pattern = r"CREATE \(p:LearningPath \{\s*id: \"(PATH-\d+)\",\s*name: \"([^\"]+)\",\s*description: \"([^\"]+)\",\s*targetAudience: \"([^\"]*)\",\s*keyCompetencies: \"([^\"]*)\",\s*estimatedMinutes: (\d+)\s*\}\);"
    
    for match in re.finditer(path_pattern, cypher_script):
        path_id, name, description, target_audience, key_competencies, minutes = match.groups()
        learning_paths[path_id] = {
            "id": path_id,
            "name": name,
            "description": description,
            "targetAudience": target_audience,
            "keyCompetencies": key_competencies.split(";") if key_competencies else [],
            "estimatedMinutes": int(minutes),
            "concepts": []  # Will be populated later
        }
    
    # Extract node-to-node relationships
    node_relationship_pattern = r"MATCH \(a:KnowledgeNode \{id: \"(N\d+)\"\}\), \(b:KnowledgeNode \{id: \"(N\d+)\"\}\)\s*CREATE \(a\)-\[:(\w+) \{strength: (\d+), justification: \"([^\"]+)\"\}\]->\(b\);"
    
    for match in re.finditer(node_relationship_pattern, cypher_script):
        source, target, rel_type, strength, justification = match.groups()
        relationships.append({
            "source": source,
            "target": target,
            "type": rel_type,
            "strength": int(strength),
            "justification": justification
        })
    
    # Extract concept-node relationships (CONTAINS)
    concept_node_pattern = r"MATCH \(c:Concept \{id: \"(CONCEPT-\d+)\"\}\), \(n:KnowledgeNode \{id: \"(N\d+)\"\}\)\s*CREATE \(c\)-\[:CONTAINS \{sequence: (\d+)\}\]->\(n\);"
    
    concept_nodes = {}
    for match in re.finditer(concept_node_pattern, cypher_script):
        concept_id, node_id, sequence = match.groups()
        if concept_id not in concept_nodes:
            concept_nodes[concept_id] = []
        concept_nodes[concept_id].append((node_id, int(sequence)))
        
        if concept_id in concepts:
            # Add node to concept's nodes list if not already there
            if node_id not in concepts[concept_id]["nodes"]:
                concepts[concept_id]["nodes"].append(node_id)
    
    # Sort nodes in each concept by sequence
    for concept_id, nodes in concept_nodes.items():
        sorted_nodes = sorted(nodes, key=lambda x: x[1])
        if concept_id in concepts:
            concepts[concept_id]["sequence"] = [node_id for node_id, _ in sorted_nodes]
    
    # Extract path-concept relationships (INCLUDES)
    path_concept_pattern = r"MATCH \(p:LearningPath \{id: \"(PATH-\d+)\"\}\), \(c:Concept \{id: \"(CONCEPT-\d+)\"\}\)\s*CREATE \(p\)-\[:INCLUDES \{sequence: (\d+)\}\]->\(c\);"
    
    path_concepts = {}
    for match in re.finditer(path_concept_pattern, cypher_script):
        path_id, concept_id, sequence = match.groups()
        if path_id not in path_concepts:
            path_concepts[path_id] = []
        path_concepts[path_id].append((concept_id, int(sequence)))
        
        if path_id in learning_paths:
            # Add concept to path's concepts list if not already there
            if concept_id not in learning_paths[path_id]["concepts"]:
                learning_paths[path_id]["concepts"].append(concept_id)
    
    # Sort concepts in each path by sequence
    for path_id, concepts_list in path_concepts.items():
        sorted_concepts = sorted(concepts_list, key=lambda x: x[1])
        if path_id in learning_paths:
            learning_paths[path_id]["conceptSequence"] = [concept_id for concept_id, _ in sorted_concepts]
    
    # Extract concept prerequisite relationships
    prereq_pattern = r"MATCH \(a:Concept \{id: \"(CONCEPT-\d+)\"\}\), \(b:Concept \{id: \"(CONCEPT-\d+)\"\}\)\s*CREATE \(a\)-\[:PREREQUISITE_FOR\]->\(b\);"
    
    for match in re.finditer(prereq_pattern, cypher_script):
        prereq_id, concept_id = match.groups()
        relationships.append({
            "source": prereq_id,
            "target": concept_id,
            "type": "PREREQUISITE_FOR",
            "strength": 4,
            "justification": "Prerequisite concept"
        })
    
    st.success(f"Extracted {len(knowledge_nodes)} knowledge nodes, {len(concepts)} concepts, {len(learning_paths)} learning paths, and {len(relationships)} relationships")
    
    return {
        "knowledge_nodes": knowledge_nodes,
        "concepts": concepts,
        "learning_paths": learning_paths,
        "relationships": relationships
    }

def build_networkx_graph(graph_data):
    """
    Build a NetworkX graph from the parsed data
    """
    G = nx.DiGraph()
    
    # Add knowledge nodes
    for node_id, node_data in graph_data["knowledge_nodes"].items():
        # Create a copy of node_data to avoid modifying the original
        attrs = dict(node_data)
        attrs["label"] = node_data["title"]
        attrs["type"] = "KnowledgeNode"
        G.add_node(node_id, **attrs)
    
    # Add concept nodes
    for concept_id, concept_data in graph_data["concepts"].items():
        # Create a copy of concept_data to avoid modifying the original
        attrs = dict(concept_data)
        attrs["label"] = concept_data["name"]
        attrs["type"] = "Concept"
        G.add_node(concept_id, **attrs)
    
    # Add learning path nodes
    for path_id, path_data in graph_data["learning_paths"].items():
        # Create a copy of path_data to avoid modifying the original
        attrs = dict(path_data)
        attrs["label"] = path_data["name"]
        attrs["type"] = "LearningPath"
        G.add_node(path_id, **attrs)
    
    # Add node-to-node relationships
    for rel in graph_data["relationships"]:
        if rel["source"] in G and rel["target"] in G:
            G.add_edge(rel["source"], rel["target"], 
                      relation=rel["type"],
                      strength=rel["strength"],
                      justification=rel["justification"])
    
    # Add concept-node relationships
    for concept_id, concept_data in graph_data["concepts"].items():
        if "sequence" in concept_data:
            for i, node_id in enumerate(concept_data["sequence"]):
                if node_id in G:
                    G.add_edge(concept_id, node_id, 
                              relation="CONTAINS",
                              sequence=i+1)
    
    # Add path-concept relationships
    for path_id, path_data in graph_data["learning_paths"].items():
        if "conceptSequence" in path_data:
            for i, concept_id in enumerate(path_data["conceptSequence"]):
                if concept_id in G:
                    G.add_edge(path_id, concept_id, 
                              relation="INCLUDES",
                              sequence=i+1)
    
    return G

def get_node_color(node_type, difficulty=None):
    """Get a color based on node type and difficulty"""
    if node_type == "KnowledgeNode":
        if difficulty == "Beginner":
            return "#8dd3c7"  # Light teal
        elif difficulty == "Intermediate":
            return "#fb8072"  # Light red
        elif difficulty == "Advanced":
            return "#bebada"  # Light purple
        else:
            return "#66c2a5"  # Default teal
    elif node_type == "Concept":
        return "#fc8d62"  # Orange
    elif node_type == "LearningPath":
        return "#8da0cb"  # Blue
    else:
        return "#cccccc"  # Default gray

def create_pyvis_graph(G, filter_types=None, filter_node_ids=None, filter_relationships=None, height="750px", width="100%", neighborhood_degree=0):
    """
    Create an interactive PyVis graph from NetworkX graph
    
    Parameters:
    - G: NetworkX graph
    - filter_types: List of node types to include (e.g., ["Concept", "KnowledgeNode"])
    - filter_node_ids: List of specific node IDs to include
    - filter_relationships: List of relationship types to include
    - height: Height of the graph visualization
    - width: Width of the graph visualization
    - neighborhood_degree: Include neighbors up to this degree from filter_node_ids
    
    Returns:
    - HTML file path of the generated PyVis graph
    """
    # Create a copy of G to filter
    if filter_types or filter_node_ids or filter_relationships:
        subgraph = nx.DiGraph()
        
        # First determine which nodes to include
        nodes_to_include = set()
        
        if filter_node_ids:
            # Start with specified nodes
            for node_id in filter_node_ids:
                if node_id in G:
                    nodes_to_include.add(node_id)
            
            # Add neighbors up to specified degree
            if neighborhood_degree > 0:
                for node_id in list(nodes_to_include):
                    neighbors = set()
                    # Get successors (outgoing)
                    for i in range(neighborhood_degree):
                        for n in list(neighbors) + [node_id]:
                            if n in G:
                                neighbors.update(G.successors(n))
                    # Get predecessors (incoming)
                    for i in range(neighborhood_degree):
                        for n in list(neighbors) + [node_id]:
                            if n in G:
                                neighbors.update(G.predecessors(n))
                    nodes_to_include.update(neighbors)
        
        if filter_types:
            # Add nodes of specified types
            for node in G.nodes():
                if G.nodes[node].get("type") in filter_types:
                    nodes_to_include.add(node)
        
        # If no filters were applied to nodes, include all nodes
        if not filter_node_ids and not filter_types:
            nodes_to_include = set(G.nodes())
        
        # Add nodes to subgraph
        for node in nodes_to_include:
            subgraph.add_node(node, **G.nodes[node])
        
        # Add edges between included nodes based on relationship filter
        for u, v, data in G.edges(data=True):
            if u in nodes_to_include and v in nodes_to_include:
                if not filter_relationships or data.get("relation") in filter_relationships:
                    subgraph.add_edge(u, v, **data)
    else:
        # Use the whole graph if no filters
        subgraph = G
    
    # Create PyVis network
    net = Network(height=height, width=width, directed=True, notebook=False, neighborhood_highlight=True)
    
    # Add nodes with properties
    for node in subgraph.nodes():
        node_data = subgraph.nodes[node]
        node_type = node_data.get("type", "Unknown")
        
        # Set node color based on type and difficulty
        if node_type == "KnowledgeNode":
            color = get_node_color(node_type, node_data.get("difficulty"))
        else:
            color = get_node_color(node_type)
        
        # Set node size based on type
        if node_type == "LearningPath":
            size = 35
        elif node_type == "Concept":
            size = 30
        else:
            size = 25
        
        # Create label with linebreaks for long text
        label = node_data.get("label", node)
        if len(label) > 20:
            # Insert linebreaks every ~20 chars
            label_parts = []
            for i in range(0, len(label), 20):
                label_parts.append(label[i:i+20])
            label = '\n'.join(label_parts)
        
        # Create title (hover text) with more details
        if node_type == "KnowledgeNode":
            title = f"<b>{node_data.get('title', node)}</b><br>"
            title += f"ID: {node}<br>"
            title += f"Difficulty: {node_data.get('difficulty', 'N/A')}<br>"
            title += f"Time: {node_data.get('estimatedMinutes', 'N/A')} min<br>"
            title += f"<hr>{node_data.get('description', '')}"
        elif node_type == "Concept":
            title = f"<b>{node_data.get('name', node)}</b><br>"
            title += f"ID: {node}<br>"
            title += f"Time: {node_data.get('estimatedMinutes', 'N/A')} min<br>"
            title += f"<hr>{node_data.get('description', '')}"
        elif node_type == "LearningPath":
            title = f"<b>{node_data.get('name', node)}</b><br>"
            title += f"ID: {node}<br>"
            title += f"Time: {node_data.get('estimatedMinutes', 'N/A')} min<br>"
            title += f"Target: {node_data.get('targetAudience', 'N/A')}<br>"
            title += f"<hr>{node_data.get('description', '')}"
        else:
            title = node
        
        # Add node to network
        net.add_node(node, label=label, title=title, color=color, size=size, 
                   shape="dot" if node_type == "KnowledgeNode" else "box")
    
    # Add edges with properties
    edge_colors = {
        "LEADS_TO": "#4682b4",
        "PRECEDES": "#d62728",
        "REQUIRES": "#9467bd",
        "RELATED_TO": "#8c564b",
        "ENABLES": "#e377c2",
        "PART_OF": "#7f7f7f",
        "SUPPORTS": "#bcbd22",
        "INFLUENCES": "#17becf",
        "INCLUDES": "#1f77b4",
        "CONTAINS": "#ff7f0e",
        "PREREQUISITE_FOR": "#d62728",
        "SPECIALIZES_TO": "#2ca02c"
    }
    
    for u, v, data in subgraph.edges(data=True):
        relation = data.get("relation", "")
        color = edge_colors.get(relation, "#999999")
        
        # Create edge label
        label = relation
        
        # Create title (hover text) with more details
        title = f"Type: {relation}<br>"
        if "strength" in data:
            title += f"Strength: {data['strength']}<br>"
        if "justification" in data:
            title += f"<hr>{data['justification']}"
        
        # Add edge to network
        net.add_edge(u, v, title=title, label=label, color=color)
    
    # Set physics options for better layout
    net.set_options("""
    {
      "physics": {
        "solver": "forceAtlas2Based",
        "forceAtlas2Based": {
          "gravitationalConstant": -100,
          "centralGravity": 0.015,
          "springLength": 150,
          "springConstant": 0.08
        },
        "minVelocity": 0.75,
        "maxVelocity": 50,
        "timestep": 0.5,
        "stabilization": {
          "enabled": true,
          "iterations": 1000
        }
      },
      "edges": {
        "arrows": {
          "to": {
            "enabled": true,
            "scaleFactor": 0.5
          }
        },
        "smooth": {
          "enabled": true,
          "type": "continuous"
        },
        "color": {
          "inherit": false
        },
        "width": 1.5
      },
      "interaction": {
        "navigationButtons": true,
        "keyboard": true,
        "tooltipDelay": 200
      }
    }
    """)
    
    # Generate file in a temp directory
    temp_dir = tempfile.mkdtemp()
    path = os.path.join(temp_dir, "pyvis_graph.html")
    net.save_graph(path)
    
    return path

def create_path_view(G, path_id):
    """Create a view of a learning path with its concepts and nodes"""
    if path_id not in G:
        st.error(f"Learning path {path_id} not found in the graph")
        return None
    
    # Extract the subgraph for this path
    path_concepts = [n for n in G.successors(path_id) if G.nodes[n].get("type") == "Concept"]
    path_concepts.sort(key=lambda c: G.edges[path_id, c].get("sequence", 0))
    
    # Create PyVis graph
    return create_pyvis_graph(G, filter_node_ids=[path_id] + path_concepts, neighborhood_degree=1, height="600px", width="100%")

def create_concept_view(G, concept_id):
    """Create a view of a concept with its knowledge nodes"""
    if concept_id not in G:
        st.error(f"Concept {concept_id} not found in the graph")
        return None
    
    # Create PyVis graph
    return create_pyvis_graph(G, filter_node_ids=[concept_id], neighborhood_degree=1, height="600px", width="100%")

def create_relationships_view(G, relationship_types=None):
    """Create a view of node relationships of specified types"""
    # Create PyVis graph
    return create_pyvis_graph(G, filter_types=["KnowledgeNode"], filter_relationships=relationship_types, height="700px", width="100%")

def display_node_details(G, node_id):
    """Display detailed information about a node"""
    if node_id not in G:
        st.warning(f"Node {node_id} not found in the graph")
        return
    
    node_data = G.nodes[node_id]
    node_type = node_data.get("type", "Unknown")
    
    st.subheader(f"Node Details: {node_id}")
    
    if node_type == "KnowledgeNode":
        st.write(f"**Title:** {node_data.get('title', 'N/A')}")
        st.write(f"**Difficulty:** {node_data.get('difficulty', 'N/A')}")
        st.write(f"**Estimated Time:** {node_data.get('estimatedMinutes', 'N/A')} minutes")
        st.write(f"**Source:** {node_data.get('source_title', 'N/A')} ({node_data.get('source_lesson', 'N/A')})")
        st.write(f"**Description:** {node_data.get('description', 'N/A')}")
        
        # Find concepts that contain this node
        containing_concepts = []
        for n in G.predecessors(node_id):
            if G.nodes[n].get("type") == "Concept" and G.edges[n, node_id].get("relation") == "CONTAINS":
                containing_concepts.append((n, G.nodes[n].get("label", n)))
        
        if containing_concepts:
            st.write("**Contained in Concepts:**")
            for concept_id, concept_name in containing_concepts:
                st.write(f"- {concept_name} ({concept_id})")
        
        # Show relationships to other nodes
        outgoing = []
        for n in G.successors(node_id):
            if G.nodes[n].get("type") == "KnowledgeNode":
                rel = G.edges[node_id, n].get("relation", "RELATED_TO")
                outgoing.append((n, rel, G.nodes[n].get("label", n)))
        
        incoming = []
        for n in G.predecessors(node_id):
            if G.nodes[n].get("type") == "KnowledgeNode":
                rel = G.edges[n, node_id].get("relation", "RELATED_TO")
                incoming.append((n, rel, G.nodes[n].get("label", n)))
        
        if outgoing:
            st.write("**Outgoing Relationships:**")
            for node, rel, label in outgoing:
                st.write(f"- {rel} → {label} ({node})")
        
        if incoming:
            st.write("**Incoming Relationships:**")
            for node, rel, label in incoming:
                st.write(f"- {label} ({node}) → {rel}")
    
    elif node_type == "Concept":
        st.write(f"**Name:** {node_data.get('name', 'N/A')}")
        st.write(f"**Estimated Time:** {node_data.get('estimatedMinutes', 'N/A')} minutes")
        st.write(f"**Description:** {node_data.get('description', 'N/A')}")
        
        # Find learning paths that include this concept
        including_paths = []
        for n in G.predecessors(node_id):
            if G.nodes[n].get("type") == "LearningPath" and G.edges[n, node_id].get("relation") == "INCLUDES":
                including_paths.append((n, G.nodes[n].get("label", n)))
        
        if including_paths:
            st.write("**Included in Learning Paths:**")
            for path_id, path_name in including_paths:
                st.write(f"- {path_name} ({path_id})")
        
        # Find prerequisites and dependents
        prerequisites = []
        for n in G.predecessors(node_id):
            if G.nodes[n].get("type") == "Concept" and G.edges[n, node_id].get("relation") == "PREREQUISITE_FOR":
                prerequisites.append((n, G.nodes[n].get("label", n)))
        
        dependents = []
        for n in G.successors(node_id):
            if G.nodes[n].get("type") == "Concept" and G.edges[node_id, n].get("relation") == "PREREQUISITE_FOR":
                dependents.append((n, G.nodes[n].get("label", n)))
        
        if prerequisites:
            st.write("**Prerequisites:**")
            for concept_id, concept_name in prerequisites:
                st.write(f"- {concept_name} ({concept_id})")
        
        if dependents:
            st.write("**Dependent Concepts:**")
            for concept_id, concept_name in dependents:
                st.write(f"- {concept_name} ({concept_id})")
        
        # Show contained knowledge nodes
        contained_nodes = []
        for n in G.successors(node_id):
            if G.nodes[n].get("type") == "KnowledgeNode" and G.edges[node_id, n].get("relation") == "CONTAINS":
                seq = G.edges[node_id, n].get("sequence", 0)
                contained_nodes.append((n, seq, G.nodes[n].get("label", n)))
        
        if contained_nodes:
            st.write("**Knowledge Nodes:**")
            for node, seq, label in sorted(contained_nodes, key=lambda x: x[1]):
                st.write(f"{seq}. {label} ({node})")
    
    elif node_type == "LearningPath":
        st.write(f"**Name:** {node_data.get('name', 'N/A')}")
        st.write(f"**Target Audience:** {node_data.get('targetAudience', 'N/A')}")
        st.write(f"**Estimated Time:** {node_data.get('estimatedMinutes', 'N/A')} minutes")
        st.write(f"**Description:** {node_data.get('description', 'N/A')}")
        
        # Show key competencies
        key_competencies = node_data.get("keyCompetencies", [])
        if key_competencies:
            st.write("**Key Competencies:**")
            for competency in key_competencies:
                st.write(f"- {competency}")
        
        # Show included concepts
        included_concepts = []
        for n in G.successors(node_id):
            if G.nodes[n].get("type") == "Concept" and G.edges[node_id, n].get("relation") == "INCLUDES":
                seq = G.edges[node_id, n].get("sequence", 0)
                included_concepts.append((n, seq, G.nodes[n].get("label", n)))
        
        if included_concepts:
            st.write("**Included Concepts:**")
            for concept_id, seq, concept_name in sorted(included_concepts, key=lambda x: x[1]):
                st.write(f"{seq}. {concept_name} ({concept_id})")
        
        # Show alternative routes if any
        # TODO: Extract alternative routes

# Function to create an expandable container for the graph visualization
def create_expandable_graph(html_path, default_height=600):
    """
    Create an expandable graph container
    
    Parameters:
    - html_path: Path to the HTML file
    - default_height: Default height for the graph container
    """
    if html_path is None:
        return
    
    # Read the HTML content
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Create a container for the graph
    graph_container = st.container()
    
    # Add buttons for expanding and collapsing
    col1, col2 = st.columns([4, 1])
    with col2:
        full_screen = st.checkbox("📊 Fullscreen Graph", key=f"fullscreen_{html_path}")
    
    # Adjust the height based on the fullscreen setting
    height = 800 if full_screen else default_height
    
    # Display the graph
    with graph_container:
        components.html(html_content, height=height)

def main():
    st.title("Knowledge Graph Explorer")
    
    # File uploader for Cypher file
    uploaded_file = st.sidebar.file_uploader("Upload Cypher Script", type=["cypher", "txt"])
    
    # Allow entering file path as alternative to upload
    cypher_path = None
    # cypher_path = st.sidebar.text_input("Or Enter Cypher File Path:", "")
    
    # # Example file as fallback
    # use_example = st.sidebar.checkbox("Use Example Cypher File", value=False)
    
    # Main process
    if uploaded_file is not None:
        # Save uploaded file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".cypher") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            cypher_path = tmp_file.name
    # elif not cypher_path and use_example:
    #     cypher_path = "customer_centricity_graph.cypher"  # Default example
    
    # Process the Cypher file if provided
    if cypher_path:
        if os.path.exists(cypher_path):
            # Parse the Cypher file and build the graph
            try:
                # Use session state to cache the graph
                if 'graph_data' not in st.session_state or st.session_state['cypher_path'] != cypher_path:
                    st.session_state['graph_data'] = parse_cypher_file(cypher_path)
                    st.session_state['graph'] = build_networkx_graph(st.session_state['graph_data'])
                    st.session_state['cypher_path'] = cypher_path
                
                graph_data = st.session_state['graph_data']
                G = st.session_state['graph']
                
                # Create tabs for different views
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "Curriculum Overview", 
                    "Learning Paths", 
                    "Concepts", 
                    "Node Relationships",
                    "Node Explorer"
                ])
                
                # Tab 1: Curriculum Overview
                with tab1:
                    st.header("Curriculum Overview")
                    st.write("This visualization shows all learning paths and concepts with their relationships.")
                    
                    # Filter options
                    show_knowledge_nodes = st.checkbox("Show Knowledge Nodes", value=False)
                    
                    # Create filters
                    if show_knowledge_nodes:
                        filter_types = ["LearningPath", "Concept", "KnowledgeNode"]
                    else:
                        filter_types = ["LearningPath", "Concept"]
                    
                    # Generate and display the PyVis graph
                    html_path = create_pyvis_graph(G, filter_types=filter_types)
                    with open(html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    components.html(html_content, height=750)
                
                # Tab 2: Learning Paths
                with tab2:
                    st.header("Learning Paths Explorer")
                    
                    # Create a dropdown for selecting a learning path
                    paths = [(path_id, G.nodes[path_id]["label"]) 
                             for path_id in graph_data["learning_paths"].keys()]
                    paths.sort(key=lambda x: x[0])  # Sort by ID
                    
                    # Use a horizontal layout for selection controls
                    selected_path = st.selectbox(
                        "Select a Learning Path", 
                        options=[p[0] for p in paths],
                        format_func=lambda x: f"{x}: {dict(paths)[x]}"
                    )
                    
                    if selected_path:
                        # Use a better layout with expandable sections
                        with st.expander("Learning Path Details", expanded=True):
                            # Display path details
                            path_data = graph_data["learning_paths"][selected_path]
                            st.subheader(path_data["name"])
                            st.write(f"**ID:** {selected_path}")
                            st.write(f"**Target Audience:** {path_data.get('targetAudience', 'N/A')}")
                            st.write(f"**Estimated Time:** {path_data['estimatedMinutes']} minutes")
                            st.write(f"**Description:** {path_data['description']}")
                            
                            # List key competencies
                            if path_data.get("keyCompetencies"):
                                st.write("**Key Competencies:**")
                                for competency in path_data["keyCompetencies"]:
                                    st.write(f"- {competency}")
                            
                            # List concepts in sequence
                            if "conceptSequence" in path_data:
                                st.write("**Concepts:**")
                                for i, concept_id in enumerate(path_data["conceptSequence"]):
                                    concept_name = graph_data["concepts"][concept_id]["name"]
                                    st.write(f"{i+1}. {concept_name}")
                        
                        # Generate and display the PyVis graph with fullscreen option
                        html_path = create_path_view(G, selected_path)
                        if html_path:
                            create_expandable_graph(html_path, default_height=600)
                
                # Tab 3: Concepts
                with tab3:
                    st.header("Concepts Explorer")
                    
                    # Create a dropdown for selecting a concept
                    concepts = [(concept_id, concept_data["name"]) 
                               for concept_id, concept_data in graph_data["concepts"].items()]
                    concepts.sort(key=lambda x: x[0])  # Sort by ID
                    
                    # Use a horizontal layout for selection controls
                    selected_concept = st.selectbox(
                        "Select a Concept", 
                        options=[c[0] for c in concepts],
                        format_func=lambda x: f"{x}: {dict(concepts)[x]}"
                    )
                    
                    if selected_concept:
                        # Use a better layout with expandable sections
                        with st.expander("Concept Details", expanded=True):
                            # Display concept details
                            concept_data = graph_data["concepts"][selected_concept]
                            st.subheader(concept_data["name"])
                            st.write(f"**ID:** {selected_concept}")
                            st.write(f"**Estimated Time:** {concept_data['estimatedMinutes']} minutes")
                            st.write(f"**Description:** {concept_data['description']}")
                            
                            # List knowledge nodes
                            if "sequence" in concept_data:
                                st.write("**Knowledge Nodes:**")
                                for i, node_id in enumerate(concept_data["sequence"]):
                                    node_title = graph_data["knowledge_nodes"][node_id]["title"]
                                    node_difficulty = graph_data["knowledge_nodes"][node_id]["difficulty"]
                                    st.write(f"{i+1}. {node_title} ({node_difficulty})")
                        
                        # Generate and display the PyVis graph with fullscreen option
                        html_path = create_concept_view(G, selected_concept)
                        if html_path:
                            create_expandable_graph(html_path, default_height=600)
                
                # Tab 4: Node Relationships
                with tab4:
                    st.header("Knowledge Node Relationships")
                    
                    # Create filters for relationship types
                    relationship_types = set()
                    for rel in graph_data["relationships"]:
                        relationship_types.add(rel["type"])
                    
                    relationship_types = sorted(list(relationship_types))
                    
                    # Display filters in an expander
                    with st.expander("Relationship Filters", expanded=True):
                        selected_relationships = st.multiselect(
                            "Select Relationship Types",
                            options=relationship_types,
                            default=["LEADS_TO", "PRECEDES"] if "LEADS_TO" in relationship_types else relationship_types[:2]
                        )
                    
                    if selected_relationships:
                        # Generate and display the PyVis graph with fullscreen option
                        html_path = create_relationships_view(G, selected_relationships)
                        if html_path:
                            create_expandable_graph(html_path, default_height=700)
                    else:
                        st.info("Please select at least one relationship type to visualize.")
                
                # Tab 5: Node Explorer
                with tab5:
                    st.header("Node Explorer")
                    
                    # Create filters for node type
                    node_type_options = ["KnowledgeNode", "Concept", "LearningPath"]
                    selected_node_type = st.selectbox("Node Type", options=node_type_options)
                    
                    # Get all nodes of the selected type
                    nodes_of_type = [(node_id, G.nodes[node_id].get("label", node_id)) 
                                    for node_id in G.nodes() 
                                    if G.nodes[node_id].get("type") == selected_node_type]
                    nodes_of_type.sort(key=lambda x: x[0])  # Sort by ID
                    
                    # Create a dropdown for selecting a node
                    selected_node = st.selectbox(
                        "Select a Node", 
                        options=[n[0] for n in nodes_of_type],
                        format_func=lambda x: f"{x}: {dict(nodes_of_type)[x]}"
                    )
                    
                    if selected_node:
                        # Use expandable section for node details
                        with st.expander("Node Details", expanded=True):
                            # Display node details
                            display_node_details(G, selected_node)
                        
                        # Controls for the graph
                        neighborhood_size = st.slider("Neighborhood Size", min_value=1, max_value=3, value=1)
                        
                        # Generate and display the PyVis graph with fullscreen option
                        html_path = create_pyvis_graph(G, filter_node_ids=[selected_node], neighborhood_degree=neighborhood_size)
                        if html_path:
                            create_expandable_graph(html_path, default_height=600)
                
                # Add a data download section at the bottom
                st.sidebar.markdown("---")
                st.sidebar.subheader("Data Export")
                
                # Option to download graph data as JSON
                if st.sidebar.button("Download Graph Data (JSON)"):
                    json_str = json.dumps(graph_data, indent=2)
                    st.sidebar.download_button(
                        label="Download JSON",
                        data=json_str,
                        file_name="knowledge_graph_data.json",
                        mime="application/json"
                    )
                
                # Option to download node data as CSV
                if st.sidebar.button("Download Nodes as CSV"):
                    # Create a DataFrame from the nodes
                    node_rows = []
                    for node_id, node_data in G.nodes(data=True):
                        row = {
                            "id": node_id,
                            "type": node_data.get("type", ""),
                            "label": node_data.get("label", ""),
                            "difficulty": node_data.get("difficulty", "") if node_data.get("type") == "KnowledgeNode" else "",
                            "estimatedMinutes": node_data.get("estimatedMinutes", ""),
                            "description": node_data.get("description", "")
                        }
                        node_rows.append(row)
                    
                    node_df = pd.DataFrame(node_rows)
                    csv_data = node_df.to_csv(index=False)
                    
                    st.sidebar.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name="knowledge_graph_nodes.csv",
                        mime="text/csv"
                    )
                
                # Option to download relationships as CSV
                if st.sidebar.button("Download Relationships as CSV"):
                    # Create a DataFrame from the relationships
                    rel_rows = []
                    for u, v, data in G.edges(data=True):
                        row = {
                            "source": u,
                            "source_label": G.nodes[u].get("label", ""),
                            "source_type": G.nodes[u].get("type", ""),
                            "target": v,
                            "target_label": G.nodes[v].get("label", ""),
                            "target_type": G.nodes[v].get("type", ""),
                            "relation": data.get("relation", ""),
                            "strength": data.get("strength", ""),
                            "sequence": data.get("sequence", "")
                        }
                        rel_rows.append(row)
                    
                    rel_df = pd.DataFrame(rel_rows)
                    csv_data = rel_df.to_csv(index=False)
                    
                    st.sidebar.download_button(
                        label="Download CSV",
                        data=csv_data,
                        file_name="knowledge_graph_relationships.csv",
                        mime="text/csv"
                    )
            
            except Exception as e:
                st.error(f"Error processing the Cypher file: {str(e)}")
                st.exception(e)
        else:
            st.warning("Cypher file path not found. Please upload a file or enter a valid path.")
    else:
        st.info("Please upload a Cypher file or enter a file path to get started.")
        
        # Display some instructions
        st.markdown("""
        ## How to Use This Tool
        
        This interactive tool allows you to explore a Customer Centricity knowledge graph.
        
        To get started:
        1. Upload a Cypher script file or provide a file path
        2. The app will parse the file and build a graph
        3. Use the tabs to explore different views of the graph
        
        ### Features:
        - **Curriculum Overview**: See the entire structure of learning paths and concepts
        - **Learning Paths**: Explore individual learning paths and their concepts
        - **Concepts**: Examine concepts and their knowledge nodes
        - **Node Relationships**: Visualize how knowledge nodes are connected
        - **Node Explorer**: Deep-dive into individual nodes and their relationships
        
        All visualizations are interactive - you can zoom, pan, and click on nodes for details.
        """)

if __name__ == "__main__":
    main()