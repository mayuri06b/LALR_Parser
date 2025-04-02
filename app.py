import streamlit as st
import pandas as pd
import ast
import networkx as nx
import matplotlib.pyplot as plt

def load_transitions(file):
    transitions = {}
    content = file.getvalue().decode('utf-8')
    for line in content.splitlines():
        state, trans = line.strip().split("|")
        transitions[int(state)] = ast.literal_eval(trans)
    return transitions

def load_clr_states(file):
    clr_states = []
    content = file.getvalue().decode('utf-8')
    for line in content.splitlines():
        state, items, lookaheads = line.strip().split("|")
        items = ast.literal_eval(items)
        lookaheads = ast.literal_eval(lookaheads)
        clr_states.append((int(state), items, lookaheads))
    return clr_states

def extract_grammar(clr_states):
    """Extract grammar rules from CLR states."""
    grammar_rules = {}
    rule_id = 0
    
    for state_num, items, _ in clr_states:
        for item in items:
            if "->" in item:
                lhs, rhs = item.split("->")
                lhs = lhs.strip()
                rhs = rhs.replace("•", "").strip()
                if (lhs, rhs) not in grammar_rules.values():
                    grammar_rules[rule_id] = (lhs, rhs)
                    rule_id += 1
    
    return grammar_rules

def merge_lalr_states(transitions, clr_states):
    """Merge LALR states by finding core-equivalent states."""
    # Create a dictionary for easier lookup
    state_dict = {state: {"items": items, "lookaheads": lookaheads} 
                 for state, items, lookaheads in clr_states}
    
    # Function to extract core (production + dot position)
    def get_core(item):
        if "->" not in item:
            return item
        lhs, rhs = item.split("->")
        parts = rhs.split("•")
        return (lhs.strip(), "->", "•".join(parts[:-1]) + parts[-1].strip())
    
    # Group states with same core
    core_groups = {}
    for state, items, _ in clr_states:
        core = frozenset(get_core(item) for item in items)
        if core in core_groups:
            core_groups[core].append(state)
        else:
            core_groups[core] = [state]
    
    # Merge states with same core
    merged_states = {}
    state_mapping = {}
    merged_count = 0
    
    for core, states in core_groups.items():
        if len(states) > 1:
            merged_count += 1
            
        merged_state_id = ",".join(map(str, sorted(states)))
        for state in states:
            state_mapping[state] = merged_state_id
            
        # Combine items and lookaheads
        combined_items = set()
        combined_lookaheads = {}
        
        for state in states:
            items = state_dict[state]["items"]
            lookaheads = state_dict[state]["lookaheads"]
            
            combined_items.update(items)
            for i, item in enumerate(items):
                if item not in combined_lookaheads:
                    combined_lookaheads[item] = set()
                combined_lookaheads[item].update(lookaheads[i])
        
        merged_states[merged_state_id] = {
            "items": list(combined_items),
            "lookaheads": combined_lookaheads
        }
    
    # Update transitions based on state mapping
    merged_transitions = {}
    for state, trans in transitions.items():
        new_state = state_mapping.get(state, str(state))
        if new_state not in merged_transitions:
            merged_transitions[new_state] = {}
        
        for symbol, target in trans.items():
            merged_transitions[new_state][symbol] = state_mapping.get(target, str(target))
    
    return merged_states, merged_transitions, state_mapping, merged_count

def generate_parsing_table(merged_states, merged_transitions, grammar):
    """Generate LALR(1) Parsing Table with ACTION and GOTO."""
    table = {}
    
    for state_id, state_data in merged_states.items():
        items = state_data["items"]
        lookaheads = state_data["lookaheads"]
        table[state_id] = {}
        
        # Handle reductions
        for item in items:
            if "->" in item and item.endswith("•"):
                lhs, rhs = item.split("->")
                lhs = lhs.strip()
                rhs = rhs.replace("•", "").strip()
                
                # Find rule number
                rule_id = next((id for id, (l, r) in grammar.items() if l == lhs and r == rhs), None)
                
                if rule_id is not None:
                    for symbol in lookaheads.get(item, set()):
                        # Special case for accept
                        if lhs == "S'" and symbol == "$":
                            table[state_id][symbol] = "Accept"
                        else:
                            table[state_id][symbol] = f"R{rule_id}"
        
        # Handle shifts and gotos
        if state_id in merged_transitions:
            for symbol, target in merged_transitions[state_id].items():
                # If lowercase, it's a terminal (shift)
                if symbol.islower() or symbol == "$":
                    table[state_id][symbol] = f"S{target}"
                # Else it's a non-terminal (goto)
                else:
                    table[state_id][symbol] = target
    
    return table

# Streamlit UI
st.set_page_config(page_title="LALR Parsing Table Generator", layout="wide")
st.title("🔷 LALR Parsing Table Generator")
st.markdown("Upload transition and CLR state files to generate a parsing table.")

col1, col2 = st.columns(2)
with col1:
    trans_file = st.file_uploader("Upload Transitions File", type=["txt"])
    clr_file = st.file_uploader("Upload CLR States File", type=["txt"])

if st.button("🚀 Generate Table"):
    if trans_file and clr_file:
        # Load data
        transitions = load_transitions(trans_file)
        clr_states = load_clr_states(clr_file)
        
        # Extract grammar rules
        grammar = extract_grammar(clr_states)
        
        # Merge states for LALR
        merged_states, merged_transitions, state_mapping, merged_count = merge_lalr_states(transitions, clr_states)
        
        # Generate parsing table
        parsing_table = generate_parsing_table(merged_states, merged_transitions, grammar)
        
        # Store in session state
        st.session_state["transitions"] = transitions
        st.session_state["merged_states"] = merged_states
        st.session_state["merged_transitions"] = merged_transitions
        st.session_state["state_mapping"] = state_mapping
        st.session_state["merged_count"] = merged_count
        st.session_state["grammar"] = grammar
        st.session_state["parsing_table"] = parsing_table
        
        if merged_count > 0:
            st.success(f"✅ The grammar is LALR! {merged_count} states were merged.")
        else:
            st.warning("ℹ️ No states were merged. The grammar is LR(1).")
    else:
        st.error("Please upload both files.")

if "grammar" in st.session_state:
    # Display Grammar
    st.subheader("📜 Grammar Rules")
    grammar_rules = st.session_state["grammar"]
    for rule_id, (lhs, rhs) in grammar_rules.items():
        st.markdown(f"**R{rule_id}:** {lhs} → {rhs}")
    
    # Display State Mapping
    st.subheader("🔄 State Mapping")
    state_mapping = st.session_state["state_mapping"]
    mapping_data = {"Original State": [], "Merged State": []}
    
    for orig, merged in state_mapping.items():
        mapping_data["Original State"].append(orig)
        mapping_data["Merged State"].append(merged)
    
    mapping_df = pd.DataFrame(mapping_data)
    st.dataframe(mapping_df, height=200)
    
    # Display Merged States
    st.subheader("🧩 Merged States with Items and Lookaheads")
    merged_states = st.session_state["merged_states"]
    
    for state_id, state_data in merged_states.items():
        with st.expander(f"State {state_id}"):
            for item in state_data["items"]:
                lookaheads = state_data["lookaheads"].get(item, [])
                lookahead_str = ", ".join(lookaheads) if lookaheads else "∅"
                st.text(f"{item}  [Lookaheads: {lookahead_str}]")
    
    # Display LALR Table - with states on Y-axis and symbols on X-axis
    st.subheader("📊 LALR(1) ACTION-GOTO Table")
    parsing_table = st.session_state["parsing_table"]
    
    # Collect all symbols
    all_symbols = set()
    for actions in parsing_table.values():
        all_symbols.update(actions.keys())
    
    # Separate terminals and non-terminals
    terminals = sorted([s for s in all_symbols if s.islower() or s == "$"])
    non_terminals = sorted([s for s in all_symbols if not s.islower() and s != "$"])
    
    # Create DataFrame with states as index (Y-axis) and symbols as columns (X-axis)
    table_data = {}
    for state_id in parsing_table:
        table_data[state_id] = {}
        for symbol in terminals + non_terminals:
            table_data[state_id][symbol] = parsing_table[state_id].get(symbol, "-")
    
    df = pd.DataFrame.from_dict(table_data, orient="index")
    
    # Style the table
    def highlight_actions(val):
        color = "#e6f3ff"  # Light blue for actions
        if isinstance(val, str) and val.startswith("S"):
            return f"background-color: {color}"
        return ""
    
    def highlight_reductions(val):
        color = "#fff2e6"  # Light orange for reductions
        if isinstance(val, str) and val.startswith("R"):
            return f"background-color: {color}"
        return ""
    
    def highlight_accept(val):
        color = "#e6ffe6"  # Light green for Accept
        if val == "Accept":
            return f"background-color: {color}; font-weight: bold"
        return ""
    
    # Add headers to separate ACTION and GOTO
    action_columns = pd.MultiIndex.from_tuples([("ACTION", t) for t in terminals])
    goto_columns = pd.MultiIndex.from_tuples([("GOTO", nt) for nt in non_terminals])
    
    action_df = df[terminals].copy()
    action_df.columns = action_columns
    
    goto_df = df[non_terminals].copy()
    goto_df.columns = goto_columns
    
    final_df = pd.concat([action_df, goto_df], axis=1)
    final_df.index.name = "State"
    
    styled_df = final_df.style.applymap(highlight_actions).applymap(highlight_reductions).applymap(highlight_accept)
    
    st.dataframe(styled_df, height=400)
    
    # Visualize state transitions
    st.subheader("🔄 State Transition Graph")
    try:
        G = nx.DiGraph()
        merged_transitions = st.session_state["merged_transitions"]
        
        # Add nodes and edges
        for state in merged_states:
            G.add_node(state)
        
        for state, trans in merged_transitions.items():
            for symbol, target in trans.items():
                G.add_edge(state, target, label=symbol)
        
        # Draw graph
        plt.figure(figsize=(10, 8))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color="lightblue", node_size=1000, font_size=10)
        edge_labels = nx.get_edge_attributes(G, "label")
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
        
        st.pyplot(plt)
    except Exception as e:
        st.error(f"Error generating graph: {e}")