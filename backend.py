import os
import certifi
import operator
import uuid

from urllib.parse import urlparse
from dotenv import load_dotenv
from typing import TypedDict, Annotated

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from tools.tavily_tool import tavily_search
from tools.flight_tools import search_flights


# ============================================================
# Environment Setup
# ============================================================

load_dotenv()

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


# ============================================================
# Database Configuration
# ============================================================

def get_database_url():

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. "
            "Please add the Render External Database URL to .env"
        )

    # Render PostgreSQL requires SSL
    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = (
            f"{database_url}{separator}sslmode=require"
        )

    return database_url


# Get database URL
DATABASE_URL = get_database_url()


# ============================================================
# Safe Database Information
# ============================================================

parsed = urlparse(DATABASE_URL)

print("====================================")
print("PostgreSQL Configuration")
print("====================================")
print("Database host:", parsed.hostname)
print("Database name:", parsed.path)
print("Database user:", parsed.username)
print("Database port:", parsed.port)
print("====================================")


# ============================================================
# Groq API Configuration
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is missing. "
        "Please add it to your .env file."
    )


# ============================================================
# LLM Configuration
# ============================================================

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    api_key=GROQ_API_KEY
)


# ============================================================
# Travel State
# ============================================================

class TravelState(TypedDict):

    messages: Annotated[
        list[AnyMessage],
        operator.add
    ]

    user_query: str

    flight_results: str

    hotel_results: str

    itinerary: str

    llm_calls: int


# ============================================================
# Flight Agent
# ============================================================

def flight_agent(state: TravelState):

    print("\n✈️ Flight Agent: Searching flights...")

    query = state["user_query"]

    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,

        "messages": [
            AIMessage(
                content="Flight results fetched."
            )
        ],

        "llm_calls": (
            state.get("llm_calls", 0) + 1
        )
    }


# ============================================================
# Hotel Agent
# ============================================================

def hotel_agent(state: TravelState):

    print("🏨 Hotel Agent: Searching hotels...")

    query = (
        f"Best hotels for {state['user_query']}"
    )

    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,

        "messages": [
            AIMessage(
                content="Hotel information fetched."
            )
        ],

        "llm_calls": (
            state.get("llm_calls", 0) + 1
        )
    }


# ============================================================
# Itinerary Agent
# ============================================================

def itinerary_agent(state: TravelState):

    print(
        "🗺️ Itinerary Agent: Creating itinerary..."
    )

    # Limit external data before sending to LLM
    flight_results = str(
        state.get("flight_results", "")
    )[:3500]

    hotel_results = str(
        state.get("hotel_results", "")
    )[:3500]

    prompt = f"""
Create a practical travel itinerary.

USER REQUEST:
{state['user_query']}

FLIGHT INFORMATION:
{flight_results}

HOTEL INFORMATION:
{hotel_results}

Create a concise day-by-day itinerary.

Include:

- Morning activities
- Afternoon activities
- Evening activities
- Transportation
- Approximate daily budget

Keep the response concise.
"""

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are an expert travel planner. "
                    "Create practical and concise travel "
                    "itineraries."
                )
            ),

            HumanMessage(
                content=prompt
            )
        ]
    )

    return {
        "itinerary": response.content,

        "messages": [
            response
        ],

        "llm_calls": (
            state.get("llm_calls", 0) + 1
        )
    }


# ============================================================
# Final Response Agent
# ============================================================

def final_agent(state: TravelState):

    print(
        "🤖 Final Agent: Preparing final response..."
    )

    # Keep input small enough for Groq TPM limit
    flight_results = str(
        state.get("flight_results", "")
    )[:2000]

    hotel_results = str(
        state.get("hotel_results", "")
    )[:2000]

    itinerary = str(
        state.get("itinerary", "")
    )[:3000]

    prompt = f"""
Create the final travel plan.

USER REQUEST:
{state['user_query']}

FLIGHT INFORMATION:
{flight_results}

HOTEL INFORMATION:
{hotel_results}

ITINERARY:
{itinerary}

Return a concise answer with:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget
6. Important Travel Tips

Do not repeat unnecessary information.

Keep the final answer concise and practical.
"""

    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "You are a helpful travel planning assistant. "
                    "Give concise, practical and well-structured "
                    "answers."
                )
            ),

            HumanMessage(
                content=prompt
            )
        ]
    )

    return {
        "messages": [
            response
        ],

        "llm_calls": (
            state.get("llm_calls", 0) + 1
        )
    }


# ============================================================
# Build LangGraph
# ============================================================

graph = StateGraph(TravelState)


# ============================================================
# Add Agents
# ============================================================

graph.add_node(
    "flight_agent",
    flight_agent
)

graph.add_node(
    "hotel_agent",
    hotel_agent
)

graph.add_node(
    "itinerary_agent",
    itinerary_agent
)

graph.add_node(
    "final_agent",
    final_agent
)


# ============================================================
# Graph Edges
# ============================================================

graph.add_edge(
    START,
    "flight_agent"
)

graph.add_edge(
    "flight_agent",
    "hotel_agent"
)

graph.add_edge(
    "hotel_agent",
    "itinerary_agent"
)

graph.add_edge(
    "itinerary_agent",
    "final_agent"
)

graph.add_edge(
    "final_agent",
    END
)


# ============================================================
# PostgreSQL Checkpointer
# ============================================================

print(
    "🔗 Connecting to Render PostgreSQL..."
)

_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(
    _conn
)

checkpointer.setup()

print(
    "✅ PostgreSQL checkpointer ready."
)


# ============================================================
# Compile LangGraph
# ============================================================

travel_graph = graph.compile(
    checkpointer=checkpointer
)

print(
    "✅ Travel LangGraph compiled successfully."
)


# ============================================================
# Run Travel Agent
# ============================================================

def run_travel_agent(
    user_input: str,
    thread_id: str | None = None
):

    # Create unique thread ID
    if not thread_id:

        thread_id = (
            f"user_{uuid.uuid4().hex}"
        )

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    print(
        "\n🚀 Starting Travel Agent...\n"
    )

    # Run LangGraph
    result = travel_graph.invoke(
        {
            "messages": [
                HumanMessage(
                    content=user_input
                )
            ],

            "user_query": user_input,

            "flight_results": "",

            "hotel_results": "",

            "itinerary": "",

            "llm_calls": 0
        },

        config=config
    )

    # Get final response
    final_answer = (
        result["messages"][-1].content
    )

    print(
        "\n✅ Travel Agent completed.\n"
    )

    return {

        "thread_id": thread_id,

        "answer": final_answer,

        "flight_results": result.get(
            "flight_results",
            ""
        ),

        "hotel_results": result.get(
            "hotel_results",
            ""
        ),

        "itinerary": result.get(
            "itinerary",
            ""
        ),

        "llm_calls": result.get(
            "llm_calls",
            0
        ),
    }