"""Build the supervisor + per-category-subagent state graph.

    build_graph(repo, *, checkpoint_db_path) → CompiledGraph

Topology:
    START → supervisor ─(route_to)→ cat_<category>  (one subgraph per category)
                       └─(no route)→ END
    cat_<category> ──(returns)──→ supervisor   (consumes the hand-back, loops or ends)

The supervisor classifies + routes + tracks the ledger; each category subgraph owns
its domain's workflows. The single SqliteSaver is shared with the nested subgraphs.
"""
from __future__ import annotations

import os
import sqlite3
from functools import partial
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from agents.categories import CATEGORY_SPECS, category_node_name
from agents.category_agent import build_category_agent
from agents.nodes import route_from_supervisor, supervisor_node
from agents.state import OrchestratorState
from db.repository import Repository


def build_graph(repo: Repository, *, checkpoint_db_path: str | None = None) -> Any:
    cp_path = checkpoint_db_path or os.environ.get("CHECKPOINT_DB_PATH", "data/checkpoints.db")
    Path(cp_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cp_path, check_same_thread=False)
    saver = SqliteSaver(conn)

    g = StateGraph(OrchestratorState)
    g.add_node("supervisor", supervisor_node)

    # One category subagent subgraph per spec. Compiled without a checkpointer so each
    # inherits the parent's saver when nested.
    route_map: dict[str, str] = {}
    for cat_id, spec in CATEGORY_SPECS.items():
        node = category_node_name(cat_id)
        g.add_node(node, build_category_agent(spec, repo))
        g.add_edge(node, "supervisor")            # subagent returns control to the supervisor
        route_map[node] = node

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route_from_supervisor, {**route_map, "end": END})

    return g.compile(checkpointer=saver)
