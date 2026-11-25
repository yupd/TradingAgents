"""A-share hot-money analyst: dragon-tiger seats, fund flow and attention."""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from tradingagents.agents.analysts.turn import take_turn
from tradingagents.agents.context import get_instrument_context_from_state, get_language_instruction
from tradingagents.agents.tools import (
    get_concept_blocks,
    get_dragon_tiger_board,
    get_fund_flow,
    get_hot_stocks,
    get_northbound_flow,
)

TOOLS = (get_dragon_tiger_board, get_fund_flow, get_hot_stocks,
         get_concept_blocks, get_northbound_flow)


def create_hot_money_analyst(llm):
    def hot_money_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = get_instrument_context_from_state(state)
        system_message = (
            "你是 A 股游资与资金面分析师。判断目标股是否被短线资金主导，以及这种主导的持续性。"
            " 工具：get_dragon_tiger_board 看营业部席位与机构参与，get_fund_flow 看主力/散户方向，"
            "get_hot_stocks 看当日强势题材，get_concept_blocks 看题材归属，get_northbound_flow 看外资。"
            " 区分：机构建仓、游资接力、散户跟风、北向配置。"
            " 结论要给出：资金属性、持续性判断、拥挤度风险、可证伪信号（如席位次日卖出）。"
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
        return {"messages": [result], "hot_money_report": report}

    return hot_money_analyst_node
