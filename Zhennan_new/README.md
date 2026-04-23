# Robot-Assisted Activity System

## Project Description
This project is an integrated robot behavior framework designed for robot-assisted group activities for children. It focuses on fostering "soft skills" (e.g., Creativity, Curiosity, Growth Mindset, Collaboration) through structured but dynamic interactions. The system uses a two-stage LLM workflow:
1. **Activity Planning**: Translates a high-level description into a structured phase-by-phase plan.
2. **Interaction Management**: Dynamically adapts robot behavior in real-time based on student input and a predefined Strategy Catalog.

## Code Documents and Functions

- `app.py`: The Flask server hosting the web-based Activity Planner.
- `templates/index.html`: The frontend structure for the web-based Activity Planner.
- `static/css/style.css`: The styling for the web-based Activity Planner.
- `static/js/script.js`: The frontend logic for the web-based Activity Planner.
- `main.py`: The central execution script for the live robot interaction loop.
- `strategy_catalog.py`: Contains the library of robot behaviors (strategies). Includes logic for "Strategy Randomization" to ensure behavior variety when multiple triggers overlap.
- `interaction_manager.py`: Handles individual conversation turns. It uses an LLM to interpret student input and decide which robot strategy and spoken response to apply next.
- `activity_planner.py`: Generates a structured JSON activity plan from a user's description.
- `llm_client.py`: A wrapper for LLM API calls.
- `activity_plan.json`: Stores the current activity's structure (editable via the web interface).
- `requirements.txt`: Lists the Python dependencies.
- `test_randomization.py`: A utility script to verify strategy randomization logic.
- `.env`: Stores environment variables such as API keys.

## How to Run in a Virtual Environment

1. **Create a Virtual Environment**:
   ```bash
   python3 -m venv .venv
   ```

2. **Activate the Virtual Environment**:
   - On Mac/Linux:
     ```bash
     source .venv/bin/activate
     ```
   - On Windows:
     ```bash
     .venv\Scripts\activate
     ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**:
   Ensure you have a `.env` file in the root directory with your API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

5. **Run the Activity Planner (Web Interface)**:
   ```bash
   python3 app.py
   ```
   Open your browser to `http://localhost:5000`. Here you can generate, review, and edit your activity plan.

6. **Run the Live Interaction (Terminal)**:
   Once you have saved your plan in the web interface, run the interaction:
   ```bash
   python3 main.py
   ```
   (Wait for the prompt to load the saved `activity_plan.json`).

7. **(Optional) Run Verification Tests**:
   To check strategy randomization logic:
   ```bash
   python3 test_randomization.py
   ```
