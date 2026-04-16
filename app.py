# app.py
import streamlit as st
from chatbot import build_chatbot
from feedback import record_feedback, get_statistics

bot = build_chatbot()

st.title("UAlberta Math & Stats Assistant")

# Show feedback statistics in sidebar
with st.sidebar:
    st.header("Feedback Stats")
    stats = get_statistics()
    if stats["total_feedback"] > 0:
        st.metric("Total Responses Rated", stats["total_feedback"])
        st.metric("Positive", stats["positive"])
        st.metric("Negative", stats["negative"])
    else:
        st.write("Be the first to give feedback!")

    st.markdown("---")
    st.markdown("### Quick Stats")
    st.write(f"- Programs: Best performing")
    st.write(f"- Courses: Need more content")

# Initialize session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Display chat history
for message in st.session_state.chat_history:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.write(message["content"])
    else:
        with st.chat_message("assistant"):
            st.write(message["content"])

            # Show feedback buttons for the last bot response
            if message == st.session_state.chat_history[-1]:
                st.markdown("**Was this response helpful?**")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("👍 Yes"):
                        record_feedback(
                            question=message.get("question", ""),
                            response=message["content"][:1000],
                            rating=1,
                        )
                        st.success("Thanks!")
                        st.rerun()
                with col2:
                    if st.button("👎 No"):
                        record_feedback(
                            question=message.get("question", ""),
                            response=message["content"][:1000],
                            rating=-1,
                        )
                        st.info("Thanks for the feedback!")
                        st.rerun()

# Chat input - auto-submits on Enter
prompt = st.chat_input("Ask a question...")

if prompt:
    # Add user message to history
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    # Get bot response
    response = bot(prompt)

    # Add bot response to history
    st.session_state.chat_history.append(
        {"role": "assistant", "content": response, "question": prompt}
    )

    st.rerun()

# Clear chat button at the bottom
if st.session_state.chat_history:
    st.markdown("---")
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()
