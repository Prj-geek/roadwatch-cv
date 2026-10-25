## Install and Run

### Prerequisites

- Windows 10/11
- Python 3.10 installed
- Internet connection for the initial model download

### Setup

Run these commands in PowerShell from the project root:

```powershell
# Create a virtual environment using Python 3.10
py -3.10 -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install project dependencies
python -m pip install -r requirements.txt

# Start the application
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

On the first analysis, Ultralytics downloads the `yolo11n.pt` model weights. An internet connection is required for this initial download. Later runs use the locally cached weights. Inference currently runs on CPU.

### Running the Project Again

Whenever you open a new PowerShell terminal, run:

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

### Troubleshooting

- If Python 3.10 is not found, install it before running the setup commands.
- If PowerShell blocks activation, review your script execution policy or activate the environment through Command Prompt.
- If dependencies fail to install, check the error output before starting the application.
