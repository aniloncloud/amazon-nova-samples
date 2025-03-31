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
```
cd python-server
python3 -m venv .venv
```
Mac
```
source .venv/bin/activate
```
Windows
```
.venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Start server

1. Start Python WebSocket server:
```bash
python server.py --host localhost --port 8081
```

### Start the Javascript fontend (without authentication)

Open the `javascript-client/index.html` in Chrome

### Start REACT frontend (with authentication)
1. Navigate to the `react-client` folder
```
cd react-client
```
2. Install
```
npm install
```

3. Set up environment variables by renaming the .env-template file to .env. Fill in the required Cognito user pool information and the WebSocket URL.

If you've started the WebSocket from the previous step, set WS_URL to ws://localhost:8081

4. Run
```
npm Start
```