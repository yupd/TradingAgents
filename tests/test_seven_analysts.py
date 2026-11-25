from tests.test_graph_end_to_end import ScriptedModel
from tradingagents.agents import (
    create_hot_money_analyst,
    create_lockup_analyst,
    create_policy_analyst,
)
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup

DEFAULT = ("market", "social", "news", "fundamentals", "policy", "hot_money", "lockup")


def test_factories_exist():
    for factory in (create_policy_analyst, create_hot_money_analyst, create_lockup_analyst):
        assert callable(factory)


def test_setup_accepts_seven():
    llm = ScriptedModel()
    logic = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)
    graph = GraphSetup(llm, llm, logic, max_tool_rounds=2).setup_graph(list(DEFAULT))
    assert {"Policy Analyst", "Hot Money Analyst", "Lockup Analyst"} <= set(graph.nodes)
