# Contributing to Gigi

Thank you for your interest in contributing to the **Gigi Social Robot Platform**! We welcome contributions from researchers, roboticists, educators, software engineers, and enthusiasts.

---

## 🛠️ Development Setup

1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/gogordon-iu/gigi.git
   cd gigi
   ```

2. **Git LFS (Large File Storage)**:
   The repository uses Git LFS to track large neural models (`.onnx`, `.rknn`, `.mdl`, `.fst`, etc.):
   ```bash
   git lfs install
   git lfs pull
   ```

3. **Virtual Environment & Dependencies**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   pip install --upgrade pip setuptools wheel
   pip install -e ".[dev]"
   ```

4. **Verify Your Setup**:
   ```bash
   python -m unittest tests/test_bluetooth_compatibility.py
   python -m unittest tests/test_activity_logic.py
   python -m unittest tests/test_local_subsystems.py
   ```

---

## 📐 Development Guidelines

- **Clean Architecture**: Follow the layered subsystem layout (`gigi.core`, `gigi.hal`, `gigi.perception`, `gigi.expression`, `gigi.interaction`, `gigi.activities`).
- **Hardware Abstraction**: All hardware interactions (servos, camera, audio, GPIO, I2C) must gracefully fall back to simulated mock providers when running on development workstations.
- **Motor Calibration Safety**: Never bypass motor calibration safety checks. Physical robot servos must remain locked out until calibrated.
- **No Hardcoded Credentials**: Never commit passwords, private keys, device-specific calibration files, or private network IPs. Use environment variables and `.env.example`.
- **Git Hygiene**:
  - Keep commits focused and descriptive.
  - Do not commit large binary audio caches or model weights directly into standard Git trees; use `.gitignore` and Git LFS.

---

## 🧪 Testing Guidelines

Before opening a pull request:
1. Ensure all tests pass:
   ```bash
   python -m unittest discover tests "test_*.py"
   ```
2. If introducing new features or activities, write corresponding unit tests under `tests/`.
3. Verify formatting and linting:
   ```bash
   ruff check src/ tests/
   ```

---

## 🚀 Submitting a Pull Request

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit your changes with clear commit messages.
3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```
4. Open a Pull Request against `main`. Provide a concise summary of what changed and how you verified it.

---

## 📄 License

By contributing to Gigi, you agree that your contributions will be licensed under the project's [Apache-2.0 License](LICENSE).
