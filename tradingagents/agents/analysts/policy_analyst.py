"""A-share policy analyst: regulation, industrial policy and their market transmission."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import get_global_news, get_industry_comparison, get_news

TOOLS = (get_news, get_global_news, get_industry_comparison)


def create_policy_analyst(llm):
    def policy_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)
        system_message = (
            "你是 A 股政策分析师。从政策与监管信息判断目标公司的中期影响，而不是复述新闻。"
            " 重点：产业政策、监管处罚、补贴/税收、地方政策、行业准入；区分已落地与传言。"
            " 用 get_news 看个股政策相关新闻，get_global_news 看宏观与监管动向，"
            "get_industry_comparison 判断行业是否处于政策受益/受压位置。"
            " 结论要给出：政策方向（支持/中性/收紧）、影响路径、时间维度、可证伪信号。"
            + get_language_instruction()
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a helpful AI assistant, collaborating with other assistants."
             " Use the provided tools to progress towards answering the question."
             " Report what your tools support; another agent decides the trade."
             " You have access to the following tools: {tool_names}."
             " Today's date is {current_date}; treat it as 'now' for all analysis and tool-call date ranges."
             " {instrument_context}\n{system_message}"),
            MessagesPlaceholder(variable_name="messages"),
        ])
        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join(t.name for t in TOOLS))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)
        result, report = take_turn(prompt, llm, TOOLS, state["messages"])
        return {"messages": [result], "policy_report": report}

    return policy_analyst_node
