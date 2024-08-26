import json
import yaml
from flask import Flask, request, render_template, send_file, session, redirect, url_for
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_folder_name(folders, parent_id):
    """Recursively find the folder name using parentId."""
    for folder in folders:
        if folder['_id'] == parent_id:
            return folder['name']
    return None



def convert_insomnia_to_openapi(insomnia_data):
    openapi_data = {
        "openapi": "3.0.0",
        "info": {
            "title": insomnia_data.get("name", "API Documentation"),
            "version": "1.0.0"
        },
        "paths": {},
        "components": {
            "schemas": {},
            "responses": {}
        },
        "tags": []
    }

    folders = [res for res in insomnia_data['resources'] if res['_type'] == 'request_group']
    requests = [res for res in insomnia_data['resources'] if res['_type'] == 'request']

    for request in requests:
        method = request.get('method', '').lower()
        path = request.get('url', '').replace("{{base_url}}", "")
        path = path.replace(":id", "{id}")

        if path not in openapi_data['paths']:
            openapi_data['paths'][path] = {}

        folder_name = get_folder_name(folders, request['parentId'])
        if folder_name and folder_name not in [tag['name'] for tag in openapi_data['tags']]:
            openapi_data['tags'].append({"name": folder_name})

        parameters = []
        for param in request.get('parameters', []):
            param_in = 'query' if param.get('type') == 'query' else 'path'
            parameters.append({
                "name": param['name'],
                "in": param_in,
                "required": param.get('required', False),
                "schema": {
                    "type": "string"
                }
            })

        for path_param in request.get('pathParameters', []):
            parameters.append({
                "name": path_param['name'],
                "in": "path",
                "required": True,
                "schema": {
                    "type": "string"
                }
            })

        request_body = None
        if method in ['post', 'put', 'patch']:
            request_body = {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "example": json.loads(request.get('body', {}).get('text', '{}'))
                        }
                    }
                }
            }

        openapi_data['paths'][path][method] = {
            "tags": [folder_name] if folder_name else [],
            "summary": request.get('name', ''),
            "description": request.get('description', ''),
            "parameters": parameters,
            "responses": {
                "200": {
                    "description": "Successful operation",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object"
                            }
                        }
                    }
                }
            },
            "requestBody": request_body
        }

    return openapi_data

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return "No file part", 400
        file = request.files['file']
        if file.filename == '':
            return "No selected file", 400

        insomnia_data = json.load(file)
        openapi_data = convert_insomnia_to_openapi(insomnia_data)

        yaml_output = yaml.dump(openapi_data, default_flow_style=False)
        
        # Store YAML content in session for later download
        session['yaml_output'] = yaml_output
        return redirect(url_for('download_page'))

    return render_template('index.html')

@app.route('/download')
def download_page():
    return render_template('download.html')

@app.route('/download_yaml')
def download_yaml():
    yaml_output = session.get('yaml_output')
    if not yaml_output:
        return redirect(url_for('index'))
    
    yaml_bytes = BytesIO(yaml_output.encode('utf-8'))
    yaml_bytes.seek(0)
    
    return send_file(
        yaml_bytes,
        mimetype='application/x-yaml',
        as_attachment=True,
        download_name='openapi.yaml'
    )

if __name__ == "__main__":
    app.run(debug=True)