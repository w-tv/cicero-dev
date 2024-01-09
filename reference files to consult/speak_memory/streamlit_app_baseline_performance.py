from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
from streamlit.components.v1 import html
import streamlit as st
import psutil, os
st.caption(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.<br>
Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.""", unsafe_allow_html=True)
print(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.
Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.""")
