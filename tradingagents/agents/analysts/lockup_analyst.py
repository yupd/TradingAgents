"""A-share lockup and shareholder-change analyst: supply overhang and insider direction."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import (
    get_fundamentals,
    get_insider_transactions,
    get_lockup_expiry,
    get_news,
)

TOOLS = (get_lockup_expiry, get_insider_transactions, get_fundamentals, get_news)


def create_lockup_analyst(llm):
    def lockup_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)
        system_message = (
            "你是 A 股解禁与股东行为分析师。评估未来供给压力与内部人方向。"
            " 工具：get_lockup_expiry 看未来 90 天解禁规模，get_insider_transactions 看股东/高管增减持，"
            "get_fundamentals 看股本与估值，get_news 看解禁/减持公告。"
            " 注意：解禁不等于减持；区分定增解禁、首发解禁、股权激励解禁；关注大股东与创投的减持动机。"
            " 结论要给出：供给压力等级、关键日期、内部人方向、可证伪信号。"
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
        return {"messages": [result], "lockup_report": report}

    return lockup_analyst_node
