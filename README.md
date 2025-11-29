# FRBSF Economic Letters Analyzer

A web application that scrapes economic letters from the Federal Reserve Bank of San Francisco and provides AI-powered insights using AWS Bedrock Claude.

## Features

- 🏦 **Web Scraping**: Automatically fetches the latest economic letters from FRBSF
- 🤖 **AI Insights**: Uses AWS Bedrock Claude Sonnet model for intelligent analysis
- 🎨 **Modern UI**: Vue.js frontend with Vuetify Material Design components
- 🚀 **Fast API**: High-performance FastAPI backend
- 📱 **Responsive**: Works on desktop and mobile devices

## Technology Stack

- **Backend**: FastAPI, Python 3.11+
- **Frontend**: Vue.js 3, Vuetify 3, Vue Router 4
- **AI/ML**: AWS Bedrock (Claude Sonnet 4)
- **Web Scraping**: BeautifulSoup4, Requests
- **Package Management**: UV

## Prerequisites

- Python 3.11+
- UV package manager
- AWS EC2 instance with appropriate IAM role for Bedrock access
- Internet connection for scraping FRBSF website

## Installation & Setup

1. **Clone and navigate to the project**:
   ```bash
   cd /root/projects/frbsf-economic-letters
   ```

2. **Install dependencies** (already done if using UV):
   ```bash
   uv sync
   ```

3. **Run the application**:
   ```bash
   uv run python run.py
   ```

4. **Access the application**:
   - Main app: http://localhost:8000
   - API docs: http://localhost:8000/docs

## Usage

### Loading Economic Letters
1. Open the application in your browser
2. Click "Load Latest Letters" to scrape the latest economic letters from FRBSF
3. Browse through the available letters

### Getting AI Insights
1. Click "View & Analyze" on any letter
2. Read the full letter content
3. Ask questions in the AI Insights panel
4. Get intelligent analysis powered by Claude Sonnet

### Example Questions
- "What are the key economic indicators mentioned?"
- "What does this mean for monetary policy?"
- "How might this affect inflation expectations?"
- "What are the implications for financial markets?"

## API Endpoints

- `GET /`: Serve the Vue.js frontend
- `GET /api/letters`: Fetch all economic letters
- `POST /api/insights`: Generate AI insights for letter content

## Project Structure

```
frbsf-economic-letters/
├── main.py              # FastAPI application
├── run.py               # Startup script
├── static/
│   └── index.html       # Vue.js frontend
├── pyproject.toml       # UV project configuration
└── README.md           # This file
```

## Configuration

The application is configured to use:
- **AWS Region**: us-east-1
- **Bedrock Model**: us.anthropic.claude-sonnet-4-20250514-v1:0
- **Server Port**: 8000
- **Host**: 0.0.0.0 (accessible from all interfaces)

## AWS Bedrock Setup

The application assumes you're running on an EC2 instance with an IAM role that has permissions to:
- Access AWS Bedrock
- Invoke the Claude Sonnet model

No additional AWS credentials configuration is needed when running on EC2 with proper IAM roles.

## Development

To modify the application:

1. **Backend changes**: Edit `main.py`
2. **Frontend changes**: Edit `static/index.html`
3. **Dependencies**: Use `uv add <package>` to add new packages

## Troubleshooting

### Common Issues

1. **Scraping fails**: Check if FRBSF website structure has changed
2. **Bedrock errors**: Verify IAM permissions and model availability
3. **Port conflicts**: Change port in `run.py` if 8000 is occupied

### Logs

The application logs to console. Check for:
- Scraping errors
- Bedrock API errors
- Network connectivity issues

## License

This project is for educational and research purposes.