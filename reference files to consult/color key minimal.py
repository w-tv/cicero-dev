import streamlit as st
values = [
  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 18, 95, 42, 72, 45, 56, 32, 88, 94, 93, 77, 60, 92, 58, 56, 79, 65, 34, 11, 96, 89, 33, 15, 64, 33, 93, 74, 41, 92, 55, 61, 69, 99, 25, 43, 91, 86, 14, 33, 52, 92, 77, 59, 29, 66, 37, 54, 12, 59, 15, 15, 34, 67, 82, 88, 15, 63, 100, 84, 49, 34, 66, 71, 62, 97, 98, 98, 28, 57, 35, 92, 86, 62, 78, 77, 30, 86, 18, 93, 79, 95, 74, 59, 91, 85, 94, 65, 76, 92, 25, 45, 100, 81, 32, 29, 51, 43, 14, 75],
  [56, 17, 44, 49, 63, 57, 84, 25, 92, 34, 51, 2, 98, 62, 61, 19, 63, 54, 22, 22, 97, 9, 18, 96, 47, 82, 30, 46, 36, 73, 38, 4, 23, 51, 58, 80, 62, 72, 8, 1, 78, 15, 78, 42, 37, 36, 40, 70, 85, 54, 46, 73, 10, 28, 99, 1, 19, 94, 6, 54, 45, 0, 86, 90, 48, 33, 40, 46, 87, 14, 84, 54, 38, 61, 15, 61, 96, 6, 34, 50, 9, 76, 18, 58, 76, 63, 1, 97, 97, 36, 16, 69, 75, 44, 23, 64, 1, 21, 84, 41, 50, 80, 44, 64, 81, 90, 9, 66, 89, 48],
  ["average", "nosy", "yielding", "relation", "swim", "frightened", "childlike", "redundant", "delay", "spotless", "sour", "economic", "pop", "theory", "cream", "lethal", "crawl", "synonymous", "wealth", "waste", "hallowed", "determined", "comfortable", "fowl", "earn", "rough", "horse", "drain", "righteous", "unknown", "cars", "ethereal", "boot", "spooky", "hall", "attempt", "certain", "uncovered", "possessive", "conscious", "grip", "erratic", "thick", "quixotic", "identify", "thirsty", "fluttering", "class", "strong", "space", "invincible", "versed", "quack", "delight", "angle", "cellar", "nutritious", "live", "married", "supreme", "watch", "event", "robin", "complain", "excuse", "lumber", "giddy", "blow", "mixed", "tiger", "start", "luxuriant", "remain", "marble", "utopian", "distribution", "dramatic", "last", "food", "flame", "country", "calculator", "decay", "wonder", "extend", "divergent", "heavy", "tearful", "shaggy", "string", "crate", "arm", "venomous", "coat", "wrong", "lunchroom", "protest", "quick", "zinc", "turn", "analyze", "plucky", "cry", "hapless", "prevent", "man", "carpenter", "damaged", "cub"]
]
values_transpose = [{"x": values[0][i], "y":values[1][i], "color":values[2][i]} for i, _ in enumerate(values[0]) ]
st.scatter_chart(values_transpose,x='x', y='y', color='color') #expected result: there are far too many color names to be seen in the key, even on a large monitor when the graph is maximized.