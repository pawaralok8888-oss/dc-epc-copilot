import streamlit as st

st.set_page_config(page_title="DC-EPC Copilot", layout="wide")
st.title("DC-EPC Copilot")
st.caption("Knowledge graph for data centre EPC delivery. All AI output is a draft for engineer approval.")

level = st.sidebar.selectbox("Commissioning level", ["L1", "L2", "L3", "L4", "L5"])
tier = st.sidebar.selectbox("Tier target", ["III", "IV"])

tab_graph, tab_tests, tab_alerts, tab_photos, tab_ask = st.tabs(
    ["Graph", "Tests", "Alerts", "Photos", "Ask"]
)

with tab_graph:
    st.info("Member A and C: graph view and blast-radius go here.")
with tab_tests:
    st.info("Member B: generated tests and traceability matrix go here.")
with tab_alerts:
    st.info("Deviation alerts and approve/reject buttons go here.")
with tab_photos:
    st.info("Member C: Reality Delta photo check goes here.")
with tab_ask:
    st.info("Member B: cited Q&A goes here.")
