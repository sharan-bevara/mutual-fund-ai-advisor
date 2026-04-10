import streamlit as st
import pandas as pd
import os
from openai import OpenAI
from dotenv import load_dotenv
from ranking_engine import MutualFundRanker
from prompts import SYSTEM_PROMPT, format_data_context

# Load API Key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="AI Fund Advisor", layout="wide")

# 1. Load Data
DATA_PATH = "ranking_test.csv"
if "ranker" not in st.session_state:
    st.session_state.ranker = MutualFundRanker(DATA_PATH)

# 2. State Management
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! I've loaded your data. Which category should I rank?"}]
if "prefs" not in st.session_state:
    st.session_state.prefs = {"scheme": None}

# 3. Sidebar
with st.sidebar:
    st.title("Settings")
    risk_mode = st.radio("Risk Strategy", ["Balanced", "Safer", "Aggressive"])
    st.divider()
    st.write("### Categories in your file:")
    unique_cats = list(st.session_state.ranker.df['Scheme Category'].unique())
    st.write(unique_cats)

# 4. Layout
col_chat, col_table = st.columns([1, 1])

with col_chat:
    st.subheader("💬 Chat with Advisor")
    for msg in st.session_state.messages:
        # Hide the system data context from the user UI
        if msg.get("role") != "system":
            st.chat_message(msg["role"]).write(msg["content"])

    # --- THE ONLY AI CALL HAPPENS HERE ---
    if prompt := st.chat_input("Ex: Show me Large Cap funds"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Keyword Detection
        p_low = prompt.lower()
        for s in unique_cats:
            if str(s).lower() in p_low:
                st.session_state.prefs["scheme"] = s
                break

        # Get Data if a scheme was found
        data_context = "No specific category identified."
        if st.session_state.prefs["scheme"]:
            res = st.session_state.ranker.calculate_ranks(st.session_state.prefs["scheme"], risk_mode)
            data_context = format_data_context(res)

        try:
            # Use gpt-4o-mini to avoid 429 errors on lower-tier accounts
            response = client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"DATA: {data_context}"},
                    *st.session_state.messages[-5:] # Only last 5 messages
                ]
            )
            ai_reply = response.choices[0].message.content
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.rerun() 

        except Exception as e:
            st.error(f"Advisor Error: {e}")

with col_table:
    st.subheader("📊 Ranking Results")
    if st.session_state.prefs["scheme"]:
        # Simply display the data, DO NOT call the AI again here
        results = st.session_state.ranker.calculate_ranks(st.session_state.prefs["scheme"], risk_mode)
        if not results.empty:
            st.dataframe(
                results.head(10)[['Fund Name', 'Final Score', 'AUM', 'Sharpe']], 
                use_container_width=True,
                hide_index=True
            )
        else:
            st.warning("No data found for this category.")