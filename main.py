from flask import Flask, request, jsonify, make_response, render_template_string
import graphviz
import re
import os
import argparse

BACKUP_FILE = 'editor_backup.txt'

app = Flask(__name__)

@app.route('/')
def index():
    # On startup, load saved editor code if it exists.
    try:
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            saved_code = f.read()
    except FileNotFoundError:
        saved_code = "digraph G {\n    A -> B;\n    B -> C;\n    C -> A;\n}"
    # Pass the saved code into the template.
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
       <meta charset="UTF-8">
       <title>TechLines</title>
       <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/codemirror.min.css">
       <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/theme/dracula.min.css">
       <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/addon/lint/lint.min.css">
       <style>
           html, body {
              height: 100%;
              margin: 0;
              padding: 0;
              overflow: hidden;
              font-family: sans-serif;
           }
           #container {
              display: flex;
              height: 100%;
           }
           #editor-pane {
              width: 50%;
              height: 100%;
              background-color: #2b2b2b;
           }
           #viewer-pane {
              width: 50%;
              height: 100%;
              background-color: #fff;
              display: flex;
              flex-direction: column;
           }
           #toolbar {
              padding: 10px;
              background-color: #f0f0f0;
              border-bottom: 1px solid #ccc;
           }
           #graph-container {
              flex-grow: 1;
              overflow: auto;
              padding: 10px;
           }
           .CodeMirror {
              height: 100%;
           }
       </style>
    </head>
    <body>
       <div id="container">
           <div id="editor-pane"></div>
           <div id="viewer-pane">
              <div id="toolbar">
                  <button id="download-svg">Download SVG</button>
                  <button id="download-png">Download PNG</button>
                  <button id="load-svg">Load SVG</button>
                  <!-- Hidden file input for loading an SVG -->
                  <input type="file" id="load-svg-input" accept="image/svg+xml" style="display:none">
              </div>
              <div id="graph-container"></div>
           </div>
       </div>

       <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/codemirror.min.js"></script>
       <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/addon/mode/simple.min.js"></script>
       <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/mode/clike/clike.min.js"></script>
       <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.5/addon/lint/lint.min.js"></script>
       <script src="https://unpkg.com/split.js/dist/split.min.js"></script>

       <script>
           // Debounce helper function.
           function debounce(func, wait, immediate) {
              var timeout;
              return function() {
                  var context = this, args = arguments;
                  var later = function() {
                      timeout = null;
                      if (!immediate) func.apply(context, args);
                  };
                  var callNow = immediate && !timeout;
                  clearTimeout(timeout);
                  timeout = setTimeout(later, wait);
                  if (callNow) func.apply(context, args);
              };
           }

           // Define a simple CodeMirror mode for Graphviz DOT language.
           CodeMirror.defineSimpleMode("dot", {
               start: [
                   {regex: /"(?:[^\\"]|\\.)*"?/, token: "string"},
                   {regex: /\b(?:digraph|graph|subgraph|node|edge)\b/, token: "keyword"},
                   {regex: /\/\/.*/, token: "comment"},
                   {regex: /\/\*/, token: "comment", next: "comment"},
                   {regex: /->|--/, token: "operator"},
                   {regex: /[{}[\];,]/, token: "bracket"},
                   {regex: /[a-zA-Z_]\w*/, token: "variable"},
                   {regex: /\s+/, token: null}
               ],
               comment: [
                   {regex: /.*?\*\//, token: "comment", next: "start"},
                   {regex: /.*/, token: "comment"}
               ],
               meta: {
                   lineComment: "//"
               }
           });

           // Custom linter: sends code to /lint and updates the lint gutter.
           function customLinter(text, updateLinting, options, cm) {
              fetch('/lint', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ code: text })
              })
              .then(response => response.json())
              .then(data => {
                  updateLinting(data.annotations);
                  if (data.annotations.length > 0) {
                      document.getElementById('graph-container').innerHTML =
                         "<div style='color:red; font-size:18px; text-align:center; margin-top:20px;'>syntax error</div>";
                  } else {
                      renderGraph();
                  }
              })
              .catch(error => {
                  console.error('Error linting code:', error);
                  updateLinting([]);
                  renderGraph();
              });
              return [];
           }

           // Initialize CodeMirror in the left pane with linting and our custom "dot" mode.
           var editor = CodeMirror(document.getElementById('editor-pane'), {
              value: {{ saved_code|tojson }},
              mode: "dot",
              theme: "dracula",
              lineNumbers: true,
              gutters: ["CodeMirror-lint-markers", "CodeMirror-linenumbers"],
              lint: {
                 getAnnotations: customLinter,
                 async: true
              }
           });

           // Auto-save: send the current code to /save (debounced).
           var autoSave = debounce(function() {
              var code = editor.getValue();
              fetch('/save', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ code: code })
              }).catch(err => console.error('Auto-save failed:', err));
           }, 1000);

           // Trigger auto-save on every change.
           editor.on("change", function() {
              autoSave();
           });

           // Render the graph by sending code to the /render endpoint.
           function renderGraph() {
              var code = editor.getValue();
              fetch('/render', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ code: code })
              })
              .then(response => response.json())
              .then(data => {
                  document.getElementById('graph-container').innerHTML = data.svg;
              })
              .catch(error => {
                  console.error('Error rendering graph:', error);
              });
           }

           // Download SVG file.
           document.getElementById('download-svg').addEventListener('click', function() {
              var code = editor.getValue();
              fetch('/download-svg', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ code: code })
              })
              .then(response => response.blob())
              .then(blob => {
                  var url = window.URL.createObjectURL(blob);
                  var a = document.createElement('a');
                  a.href = url;
                  a.download = 'graph.svg';
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  window.URL.revokeObjectURL(url);
              })
              .catch(error => {
                  console.error('Error downloading SVG:', error);
              });
           });

           // Download PNG file.
           document.getElementById('download-png').addEventListener('click', function() {
              var code = editor.getValue();
              fetch('/download-png', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ code: code })
              })
              .then(response => response.blob())
              .then(blob => {
                  var url = window.URL.createObjectURL(blob);
                  var a = document.createElement('a');
                  a.href = url;
                  a.download = 'graph.png';
                  document.body.appendChild(a);
                  a.click();
                  a.remove();
                  window.URL.revokeObjectURL(url);
              })
              .catch(error => {
                  console.error('Error downloading PNG:', error);
              });
           });

           // Load SVG: when the user clicks "Load SVG", trigger the file input.
           document.getElementById('load-svg').addEventListener('click', function() {
              document.getElementById('load-svg-input').click();
           });

           // When an SVG file is selected, read and parse it.
           document.getElementById('load-svg-input').addEventListener('change', function(e) {
              var file = e.target.files[0];
              if (!file) return;
              var reader = new FileReader();
              reader.onload = function(e) {
                  var svgText = e.target.result;
                  // Parse the SVG text to a DOM object.
                  var parser = new DOMParser();
                  var xmlDoc = parser.parseFromString(svgText, "image/svg+xml");
                  // Look for our embedded dot code.
                  var metadataElem = xmlDoc.getElementById("graphviz-dot");
                  if (metadataElem) {
                      var dotCode = metadataElem.textContent;
                      // Validate the code by sending it to /lint.
                      fetch('/lint', {
                          method: 'POST',
                          headers: {'Content-Type': 'application/json'},
                          body: JSON.stringify({ code: dotCode })
                      })
                      .then(response => response.json())
                      .then(data => {
                          if (data.annotations && data.annotations.length > 0) {
                              alert("The embedded DOT code in the SVG has syntax errors and will not be loaded.");
                          } else {
                              // Load the valid DOT code into the editor.
                              editor.setValue(dotCode);
                              editor.performLint();
                          }
                      })
                      .catch(err => {
                          console.error("Error validating the loaded DOT code:", err);
                          alert("Error validating the loaded DOT code.");
                      });
                  } else {
                      alert("No embedded Graphviz DOT code found in this SVG file.");
                  }
              };
              reader.readAsText(file);
           });

           // Also attempt a final save on unload.
           window.addEventListener('unload', function() {
               var code = editor.getValue();
               if (navigator.sendBeacon) {
                   var blob = new Blob([JSON.stringify({ code: code })], { type: 'application/json' });
                   navigator.sendBeacon('/save', blob);
               } else {
                   var xhr = new XMLHttpRequest();
                   xhr.open("POST", "/save", false);
                   xhr.setRequestHeader("Content-Type", "application/json");
                   xhr.send(JSON.stringify({ code: code }));
               }
           });

           // Initialize Split.js to allow resizing between the editor and viewer panes.
           Split(['#editor-pane', '#viewer-pane'], {
              sizes: [50, 50],
              minSize: 200,
              gutterSize: 8,
              cursor: 'col-resize'
           });

           // Trigger an initial lint to render the graph.
           setTimeout(function(){ editor.performLint(); }, 100);
       </script>
    </body>
    </html>
    ''', saved_code=saved_code)

@app.route('/render', methods=['POST'])
def render_graph():
    data = request.get_json()
    code = data.get('code', '')
    try:
        src = graphviz.Source(code, engine='dot')
        svg_data = src.pipe(format='svg').decode('utf-8')
        # Fix any relative URLs in the SVG.
        svg_data = fix_svg_urls(svg_data)
        return jsonify({'svg': svg_data})
    except Exception as e:
        error_svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='400' height='50'>"
                     "<text x='10' y='25' fill='red'>Error: syntax error</text></svg>")
        return jsonify({'svg': error_svg})

@app.route('/lint', methods=['POST'])
def lint_code():
    """
    Attempts to render the Graphviz code. If an error occurs, returns an annotation with a line number (if available).
    """
    data = request.get_json()
    code = data.get('code', '')
    try:
        src = graphviz.Source(code, engine='dot')
        src.pipe(format='svg')
        return jsonify({'annotations': []})
    except Exception as e:
        message = str(e)
        match = re.search(r'line\s+(\d+)', message, re.IGNORECASE)
        line = int(match.group(1)) - 1 if match else 0
        annotation = {
            'from': {'line': line, 'ch': 0},
            'to': {'line': line, 'ch': 0},
            'message': "Syntax error",
            'severity': "error"
        }
        return jsonify({'annotations': [annotation]})

def fix_svg_urls(svg_text):
    """
    1. Converts any bare URL (in xlink:href or href) that does not start with "http://" or "https://"
       by prepending "http://".
    2. Adds target="_blank" to all <a> tags so that links open in a new window.
    """
    # Fix bare URLs in xlink:href attributes.
    svg_text = re.sub(
        r'(xlink:href)="(?!https?://)([^"]+)"',
        r'\1="http://\2"',
        svg_text
    )
    # Fix bare URLs in href attributes.
    svg_text = re.sub(
        r'(href)="(?!https?://)([^"]+)"',
        r'\1="http://\2"',
        svg_text
    )
    # Add target="_blank" to all <a ...> tags if not already present.
    def add_target(match):
        tag = match.group(0)
        if 'target=' in tag:
            return tag
        # Insert target="_blank" before the closing '>'.
        return tag[:-1] + ' target="_blank">'
    svg_text = re.sub(r'<a\b[^>]*>', add_target, svg_text)
    return svg_text

@app.route('/download-svg', methods=['POST'])
def download_svg():
    data = request.get_json()
    code = data.get('code', '')
    try:
        src = graphviz.Source(code, engine='dot')
        svg_data = src.pipe(format='svg').decode('utf-8')
        # Fix relative URLs.
        svg_data = fix_svg_urls(svg_data)

        metadata = f"<metadata id='graphviz-dot'><![CDATA[{code}]]></metadata>"
        start_index = svg_data.find("<svg")
        if start_index != -1:
            tag_end = svg_data.find(">", start_index)
            if tag_end != -1:
                svg_data = svg_data[:tag_end+1] + metadata + svg_data[tag_end+1:]
            else:
                svg_data += metadata
        else:
            svg_data = metadata + svg_data

        response = make_response(svg_data)
        response.headers['Content-Type'] = 'image/svg+xml'
        response.headers['Content-Disposition'] = 'attachment; filename=graph.svg'
        return response
    except Exception as e:
        return str(e), 500

@app.route('/download-png', methods=['POST'])
def download_png():
    """
    Returns the rendered graph as a PNG file.
    """
    data = request.get_json()
    code = data.get('code', '')
    try:
        src = graphviz.Source(code, engine='dot')
        png_data = src.pipe(format='png')
        response = make_response(png_data)
        response.headers['Content-Type'] = 'image/png'
        response.headers['Content-Disposition'] = 'attachment; filename=graph.png'
        return response
    except Exception as e:
        return str(e), 500

@app.route('/save', methods=['POST'])
def save_code():
    """
    Saves the current editor content to disk.
    This is triggered by auto-save and when the browser unloads the page.
    """
    data = request.get_json()
    code = data.get('code', '')
    try:
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            f.write(code)
        return ('', 204)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Graphviz Live Viewer')
    parser.add_argument('--host', default='127.0.0.1', help='IP address to bind on')
    parser.add_argument('--port', default=5000, type=int, help='Port to bind on')
    args = parser.parse_args()
    app.run(debug=True, host=args.host, port=args.port)
