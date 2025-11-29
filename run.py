#!/usr/bin/env python3
"""
Startup script for FRBSF Economic Letters Analyzer
"""
import uvicorn
from main import app

if __name__ == "__main__":
    print("🏦 Starting FRBSF Economic Letters Analyzer...")
    print("📊 Features:")
    print("  - Web scraping of FRBSF economic letters")
    print("  - AI-powered insights using AWS Bedrock Claude")
    print("  - Vue.js frontend with Vuetify UI")
    print("  - FastAPI backend")
    print()
    print("🌐 Access the application at: http://localhost:8888")
    print("📡 API documentation at: http://localhost:8888/docs")
    print()
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8888,
        reload=False,
        log_level="info"
    )