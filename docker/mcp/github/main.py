from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import os
import logging
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("github-mcp")

app = FastAPI(title="GitHub MCP Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_OWNER = os.environ.get("GITHUB_OWNER")
GITHUB_REPO = os.environ.get("GITHUB_REPO")
GITHUB_API_URL = "https://api.github.com"

# Headers for GitHub API requests
headers = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

@app.get("/health")
async def health():
    """Health check endpoint - just return healthy"""
    return {"status": "healthy"}

@app.post("/issues")
async def create_issue(issue: Dict[str, Any]):
    """Create a GitHub issue"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues",
                headers=headers,
                json={
                    "title": issue.get("title"),
                    "body": issue.get("body"),
                    "labels": issue.get("labels", []),
                    "assignees": issue.get("assignees", [])
                }
            )
            if response.status_code == 201:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to create issue: {response.text}"
                )
    except Exception as e:
        logger.error(f"Failed to create issue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/issues")
async def list_issues():
    """List all open issues"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GITHUB_API_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues",
                headers=headers,
                params={"state": "open"}
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to list issues: {response.text}"
                )
    except Exception as e:
        logger.error(f"Failed to list issues: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/issues/{issue_number}")
async def update_issue(issue_number: int, update: Dict[str, Any]):
    """Update a GitHub issue"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{GITHUB_API_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}",
                headers=headers,
                json=update
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to update issue: {response.text}"
                )
    except Exception as e:
        logger.error(f"Failed to update issue: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/issues/{issue_number}/comments")
async def create_comment(issue_number: int, comment: Dict[str, str]):
    """Create a comment on an issue"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_API_URL}/repos/{GITHUB_OWNER}/{GITHUB_REPO}/issues/{issue_number}/comments",
                headers=headers,
                json={"body": comment.get("body")}
            )
            if response.status_code == 201:
                return response.json()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to create comment: {response.text}"
                )
    except Exception as e:
        logger.error(f"Failed to create comment: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8003))
    logger.info(f"Starting GitHub MCP server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
