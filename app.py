import streamlit as st
import pandas as pd
import os
from openai import OpenAI
from dotenv import load_dotenv
from ranking_engine import MutualFundRanker
from prompts import SYSTEM_PROMPT, format_data_context

def parse_intent(prompt, df):
    p_low = prompt.lower()
    
    unique_cats = df['Scheme Category'].dropna().unique() if 'Scheme Category' in df.columns else []
    
    # 1. Exact/Substring matching in actual categories FIRST
    # Sort by length descending so "Large & Mid Cap" matches before "Large Cap"
    sorted_cats = sorted(unique_cats, key=lambda x: len(str(x)), reverse=True)
    for cat in sorted_cats:
        if str(cat).lower() in p_low:
            return cat
            
    # 2. Search synonyms mappings
    synonym_mapper = {
        "large & mid cap": ["large and mid", "large & mid", "large-mid"],
        "large cap": ["bluechip", "large cap", "large caps", "largecap", "large-cap", "blue chip", "nifty"],
        "elss": ["tax saver", "tax saving", "80c", "elss", "tax-saver"],
        "flexi cap": ["flexi", "flexi cap", "flexi-cap", "flexicap", "multicap", "multi cap"],
        "mid cap": ["mid cap", "mid caps", "midcap", "mid-cap"],
        "small cap": ["small cap", "small caps", "smallcap", "small-cap"],
        "liquid": ["safe sip", "liquid", "safe", "parking", "low risk"]
    }
    
    for cat_intent, syn_list in synonym_mapper.items():
        if any(syn in p_low for syn in syn_list):
            for real_cat in unique_cats:
                if cat_intent in str(real_cat).lower():
                    return real_cat
            return cat_intent
            
    # 3. Intelligent Keyword Matching for Sectoral/Thematic Funds
    ignore_words = ['fund', 'sectoral', 'thematic', 'scheme', 'equity', 'linked', 'savings', '-', '&', 'services', 'industry', 'yield', 'care']
    for cat in unique_cats:
        cat_lower = str(cat).lower()
        clean_cat = cat_lower.replace('-', ' ').replace('&', ' ').replace('(', ' ').replace(')', ' ')
        keywords = [word.strip() for word in clean_cat.split() if word.strip() not in ignore_words]
        
        for kw in keywords:
            # Match specific keywords like "technology", "pharma", "auto", "banks"
            if len(kw) >= 4 and kw in p_low.replace('-', ' '):
                return cat
            
    # 4. Specific Fund Name resolution
    if 'Fund Name' in df.columns:
        for fname in df['Fund Name'].dropna().unique():
            if len(str(fname)) > 4 and str(fname).lower() in p_low:
                return df[df['Fund Name'] == fname]['Scheme Category'].iloc[0]
                
    # 5. Specific Scheme Type resolution
    if 'Scheme Type' in df.columns:
        for stype in df['Scheme Type'].dropna().unique():
            if len(str(stype)) > 4 and str(stype).lower() in p_low:
                category_match = df[df['Scheme Type'] == stype]['Scheme Category'].iloc[0]
                return category_match
                
    return None

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

# 4. Handle User Input First
prompt = st.chat_input("Show me Large cap funds")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Intent-aware Retrieval
    detected_category = parse_intent(prompt, st.session_state.ranker.df)
    if detected_category:
        st.session_state.prefs["scheme"] = detected_category

# 5. Layout
col_chat, col_table = st.columns([1, 1])

with col_chat:
    st.subheader("💬 Chat with Advisor")
    for msg in st.session_state.messages:
        # Hide the system data context from the user UI
        if msg.get("role") != "system":
            st.chat_message(msg["role"]).write(msg["content"])
            
    # Auto-scroll to the newest message
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
            const doc = window.parent.document;
            setTimeout(() => {
                const scrollContainer = doc.querySelector('.stAppViewContainer') || doc.querySelector('.main') || doc.documentElement;
                if (scrollContainer) {
                    scrollContainer.scrollTop = scrollContainer.scrollHeight;
                }
            }, 100);
        </script>
        """,
        height=0
    )
                
with col_table:
    st.subheader("📊 Ranking Results")
    if st.session_state.prefs["scheme"]:
        # Simply display the data, DO NOT call the AI again here
        results = st.session_state.ranker.calculate_ranks(st.session_state.prefs["scheme"], risk_mode)
        if not results.empty:
            # Define columns for display
            display_cols = ['Fund Name', 'Final Score', 'AUM', 'Sharpe']
            if 'TER' in results.columns:
                display_cols.append('TER')
            if 'Sortino' in results.columns:
                display_cols.append('Sortino')
                
            df_display = results.head(10)[display_cols].copy()
            df_display.insert(0, 'Rank', range(1, len(df_display) + 1))
            
            st.dataframe(
                df_display, 
                use_container_width=True,
                hide_index=True
            )
            
            # Export Layer Implementation
            export_cols = ['Fund Name', 'Scheme Category', 'Final Score', 'AUM', 'TER', 'Sharpe', 'Sortino']
            export_cols = [c for c in export_cols if c in results.columns]
            
            csv_data = results[export_cols].to_csv(index=False)
            safe_cat = str(st.session_state.prefs["scheme"]).replace(" ", "_").lower()
            
            st.download_button(
                label="📥 Download Ranked Funds (CSV)",
                data=csv_data,
                file_name=f"{safe_cat}_ranked_funds.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("No data found for this category.")

# 6. Generate AI Response
if prompt:
    with col_chat:
        with st.spinner("Analyzing data..."):
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
