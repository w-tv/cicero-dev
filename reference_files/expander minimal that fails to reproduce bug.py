import streamlit as st
with st.expander("Example"):
  c = st.checkbox(":^)")
  st.write(":(" if c else ":)")
