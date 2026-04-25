import streamlit as st
from chatbot import build_chatbot
from feedback import record_feedback, get_statistics

bot = build_chatbot()

st.title("UAlberta Math & Stats Assistant")

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

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Render stored conversation history
for message in st.session_state.chat_history:
    if message["role"] == "user":
        with st.chat_message("user"):
            st.write(message["content"])
    else:
        with st.chat_message("assistant"):
            st.write(message["content"])

            # Feedback buttons only on the last assistant message
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

prompt = st.chat_input("Ask a question...")

if prompt:
    # Show user message immediately
    st.session_state.chat_history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # Stream the bot response — write_stream returns the full concatenated string
    with st.chat_message("assistant"):
        response = st.write_stream(bot(prompt))

    st.session_state.chat_history.append(
        {"role": "assistant", "content": response, "question": prompt}
    )
    st.rerun()

if st.session_state.chat_history:
    st.markdown("---")
    if st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()
