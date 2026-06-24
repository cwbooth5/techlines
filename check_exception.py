import graphviz
try:
    src = graphviz.Source("digraph G { A -> B }")
    src.pipe(format='svg')
except Exception as e:
    print(f"Type: {type(e)}")
    print(f"Message: {e}")
