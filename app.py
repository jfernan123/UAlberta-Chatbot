# app.py
import streamlit as st
from chatbot import build_chatbot

bot = build_chatbot()

st.title("UAlberta Math & Stats Assistant")

query = st.text_input("Ask a question:")

if query:
    result = bot({"query": query})
    st.write(result["result"])