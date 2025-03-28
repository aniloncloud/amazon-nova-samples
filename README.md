# Amazon Nova S2S Workshop

Sample code for Nova S2S workshop

## Repository Structure


## Usage Instructions

### Prerequisites
- Python 3.12+
- Node.js 14+ and npm/yarn for UI development
- AWS account with Bedrock access
- AWS credentials configured locally

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <the-folder>
```

2. Start Python virtual machine
```bash
cd python-server
python3 -m venv .venv
source .venv/bin/activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Start server

1. Start Python WebSocket server:
```bash
python server.py
```

2. Open the `javascript-client/index.html` in Chrome
