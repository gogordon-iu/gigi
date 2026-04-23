import os
import json
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
from llm_client import LLMClient
from strategy_catalog import StrategyCatalog
from activity_planner import ActivityPlanner

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Initialize components
llm_client = LLMClient()
catalog = StrategyCatalog()
planner = ActivityPlanner(llm_client, catalog)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate', methods=['POST'])
def generate_plan():
    data = request.json
    description = data.get('description')
    if not description:
        return jsonify({"error": "Description is required"}), 400
    
    plan = planner.generate_plan(description)
    if plan:
        return jsonify(plan)
    else:
        return jsonify({"error": "Failed to generate plan"}), 500

@app.route('/api/save', methods=['POST'])
def save_plan():
    data = request.json
    if not data:
        return jsonify({"error": "No data received"}), 400
    
    try:
        with open('activity_plan.json', 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "success", "message": "Plan saved to activity_plan.json"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
