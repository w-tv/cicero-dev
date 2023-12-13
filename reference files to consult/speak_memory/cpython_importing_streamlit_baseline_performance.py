from time import perf_counter_ns
nanoseconds_base : int = perf_counter_ns()
from streamlit.components.v1 import html
import streamlit as st
import psutil, os
print(f"""Streamlit app memory usage: {psutil.Process(os.getpid()).memory_info().rss // 1024 ** 2} MiB.
Time to display: {(perf_counter_ns()-nanoseconds_base)/1000/1000/1000} seconds.""")
