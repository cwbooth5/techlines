from flask import Flask, request, jsonify, make_response, render_template
from graphviz import ExecutableNotFound
import graphviz
import re
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
    return render_template('index.html', saved_code=saved_code)

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
    except ExecutableNotFound:
        error_svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='400' height='50'>"
                     "<text x='10' y='25' fill='red'>Error: Graphviz (dot) not installed on server</text></svg>")
        return jsonify({'svg': error_svg})
    except Exception as e:
        error_svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='400' height='50'>"
                     f"<text x='10' y='25' fill='red'>Error: {str(e)}</text></svg>")
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
    except ExecutableNotFound:
        return jsonify({'annotations': [{'from': {'line': 0, 'ch': 0}, 'to': {'line': 0, 'ch': 0}, 'message': 'Graphviz (dot) not installed on server', 'severity': 'error'}]})
    except Exception as e:
        message = str(e)
        match = re.search(r'line\s+(\d+)', message, re.IGNORECASE)
        line = int(match.group(1)) - 1 if match else 0
        annotation = {
            'from': {'line': line, 'ch': 0},
            'to': {'line': line, 'ch': 0},
            'message': message,
            'severity': "error"
        }
        return jsonify({'annotations': [annotation]})

# Add target="_blank" to all <a ...> tags if not already present.
def add_target(match):
    tag = match.group(0)
    if 'target=' in tag:
        return tag
    # Insert target="_blank" before the closing '>'.
    return tag[:-1] + ' target="_blank">'

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
