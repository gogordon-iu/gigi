let currentPlan = {
    activity_title: "",
    target_audience: "",
    approximate_duration: "",
    number_of_students: "",
    steps: []
};

document.getElementById('example-prompt').addEventListener('click', () => {
    document.getElementById('activity-desc').value = document.getElementById('example-prompt').innerText;
});

document.getElementById('generate-btn').addEventListener('click', async () => {
    const desc = document.getElementById('activity-desc').value;
    if (!desc) return alert("Please enter a description");

    showLoading(true);
    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: desc })
        });
        const data = await response.json();
        if (data.error) throw new Error(data.error);

        currentPlan = data;
        renderPlan();
        document.getElementById('review-section').classList.remove('hidden');
        document.getElementById('review-section').scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
        alert("Error generating plan: " + err.message);
    } finally {
        showLoading(false);
    }
});

document.getElementById('save-btn').addEventListener('click', async () => {
    updatePlanFromInputs();
    try {
        const response = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentPlan)
        });
        const data = await response.json();
        if (data.status === 'success') {
            alert("Plan saved successfully!");
        } else {
            throw new Error(data.error);
        }
    } catch (err) {
        alert("Error saving plan: " + err.message);
    }
});

document.getElementById('add-step-btn').addEventListener('click', () => {
    currentPlan.steps.push({
        step_type: "canned",
        robot_script: "Hello students!"
    });
    renderPlan();
});

function renderPlan() {
    document.getElementById('plan-title').value = currentPlan.activity_title;
    document.getElementById('plan-audience').value = currentPlan.target_audience;
    document.getElementById('plan-duration').value = currentPlan.approximate_duration;
    document.getElementById('plan-students').value = currentPlan.number_of_students || "";

    const container = document.getElementById('steps-container');
    container.innerHTML = '';

    currentPlan.steps.forEach((step, index) => {
        const card = document.createElement('div');
        card.className = `step-card glass ${step.step_type}`;

        let bodyHtml = '';
        if (step.step_type === 'canned') {
            bodyHtml = `
                <div class="step-body">
                    <label>Robot Script:</label>
                    <textarea class="step-input" data-key="robot_script">${step.robot_script}</textarea>
                </div>
            `;
        } else {
            bodyHtml = `
                <div class="step-body">
                    <label>Goal:</label>
                    <input type="text" class="step-input" data-key="goal" value="${step.goal || ''}">
                    <label>Suggested Topics (comma separated):</label>
                    <input type="text" class="step-input" data-key="suggested_topics" value="${(step.suggested_topics || []).join(', ')}">
                    <label>Closing Condition:</label>
                    <input type="text" class="step-input" data-key="closing_condition" value="${step.closing_condition || ''}">
                </div>
            `;
        }

        card.innerHTML = `
            <div class="step-header">
                <span class="step-badge">${step.step_type}</span>
                <div class="step-actions">
                    <select class="type-select" onchange="changeStepType(${index}, this.value)">
                        <option value="canned" ${step.step_type === 'canned' ? 'selected' : ''}>Canned</option>
                        <option value="open" ${step.step_type === 'open' ? 'selected' : ''}>Open</option>
                    </select>
                    <button class="danger-btn" onclick="removeStep(${index})">Remove</button>
                </div>
            </div>
            ${bodyHtml}
        `;
        container.appendChild(card);
    });
}

function updatePlanFromInputs() {
    currentPlan.activity_title = document.getElementById('plan-title').value;
    currentPlan.target_audience = document.getElementById('plan-audience').value;
    currentPlan.approximate_duration = document.getElementById('plan-duration').value;
    currentPlan.number_of_students = document.getElementById('plan-students').value;

    const cards = document.querySelectorAll('.step-card');
    cards.forEach((card, index) => {
        const inputs = card.querySelectorAll('.step-input');
        inputs.forEach(input => {
            const key = input.getAttribute('data-key');
            if (key === 'suggested_topics') {
                currentPlan.steps[index][key] = input.value.split(',').map(s => s.trim()).filter(s => s);
            } else {
                currentPlan.steps[index][key] = input.value;
            }
        });
    });
}

window.removeStep = (index) => {
    currentPlan.steps.splice(index, 1);
    renderPlan();
};

window.changeStepType = (index, newType) => {
    updatePlanFromInputs(); // Save current work
    const oldStep = currentPlan.steps[index];
    if (newType === 'canned') {
        currentPlan.steps[index] = {
            step_type: 'canned',
            robot_script: oldStep.goal || "Hello students!"
        };
    } else {
        currentPlan.steps[index] = {
            step_type: 'open',
            goal: oldStep.robot_script || "Facilitate discussion",
            suggested_topics: [],
            closing_condition: "After 2-3 students share"
        };
    }
    renderPlan();
};

function showLoading(show) {
    document.getElementById('loading-overlay').classList.toggle('hidden', !show);
}
