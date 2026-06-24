import graphviz
try:
    src = graphviz.Source("digraph G { A -> B }")
    src.pipe(format='svg')
    print("Success")
except Exception as e:
    print(f"Error: {e}")
