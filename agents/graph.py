"""Build the LangGraph state graph.

build_graph(repo, *, checkpoint_db_path) → CompiledGraph
"""
from __future__ import annotations

import os
import sqlite3
from functools import partial
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from agents.nodes import (
    agent_node,
    await_input,
    persist_step,
    plan_steps,
    render_step,
    route_after_agent,
    route_after_persist,
    route_after_render,
    route_after_validate,
    validate_step,
)
from agents.state import AgentState
from db.repository import Repository


def build_graph(repo: Repository, *, checkpoint_db_path: str | None = None) -> Any:
    cp_path = checkpoint_db_path or os.environ.get("CHECKPOINT_DB_PATH", "data/checkpoints.db")
    Path(cp_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(cp_path, check_same_thread=False)
    saver = SqliteSaver(conn)

    g = StateGraph(AgentState)

    g.add_node("agent_node", agent_node)
    g.add_node("plan_steps", plan_steps)
    g.add_node("render_step", partial(render_step, repo=repo))
    g.add_node("await_input", await_input)
    g.add_node("validate_step", partial(validate_step, repo=repo))
    g.add_node("persist_step", partial(persist_step, repo=repo))

    g.add_edge(START, "agent_node")
    g.add_conditional_edges(
        "agent_node",
        route_after_agent,
        {"plan_steps": "plan_steps", "end": END},
    )
    g.add_edge("plan_steps", "render_step")
    g.add_conditional_edges(
        "render_step",
        route_after_render,
        {
            "await_input": "await_input",
            "render_step": "render_step",
            "persist_step": "persist_step",
            "end": END,
        },
    )
    g.add_edge("await_input", "validate_step")
    g.add_conditional_edges(
        "validate_step",
        route_after_validate,
        {"render_step": "render_step", "end": END},
    )
    g.add_conditional_edges(
        "persist_step",
        route_after_persist,
        {"render_step": "render_step", "end": END},
    )

    return g.compile(checkpointer=saver)
