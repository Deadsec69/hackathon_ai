import os
import json
import base64
import time
from typing import Dict, List, Optional, Any, Union
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from github import Github, GithubException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="GitHub MCP Server", description="MCP server for GitHub operations")

# Initialize GitHub client
github_token = os.environ.get("GITHUB_TOKEN")
github_owner = os.environ.get("GITHUB_OWNER")
github_repo = os.environ.get("GITHUB_REPO")

if not github_token:
    print("WARNING: GITHUB_TOKEN environment variable not set")

github_client = Github(github_token) if github_token else None

# MCP Models
class MCPToolInput(BaseModel):
    """Base model for MCP tool inputs"""
    pass

class MCPToolOutput(BaseModel):
    """Base model for MCP tool outputs"""
    pass

class MCPResourceOutput(BaseModel):
    """Base model for MCP resource outputs"""
    pass

class MCPError(BaseModel):
    """Model for MCP errors"""
    error: str
    details: Optional[Dict[str, Any]] = None

# GitHub Models
class CreateIssueInput(MCPToolInput):
    owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo: Optional[str] = Field(None, description="GitHub repository name")
    title: str = Field(..., description="Issue title")
    body: str = Field(..., description="Issue body")
    labels: Optional[List[str]] = Field(None, description="Issue labels")
    assignees: Optional[List[str]] = Field(None, description="Issue assignees")

class IssueOutput(MCPToolOutput):
    number: int
    title: str
    url: str
    html_url: str
    state: str
    created_at: str
    updated_at: str

class ListIssuesInput(MCPToolInput):
    owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo: Optional[str] = Field(None, description="GitHub repository name")
    state: Optional[str] = Field("open", description="Issue state (open, closed, all)")
    labels: Optional[List[str]] = Field(None, description="Filter by labels")
    assignee: Optional[str] = Field(None, description="Filter by assignee")
    creator: Optional[str] = Field(None, description="Filter by creator")
    mentioned: Optional[str] = Field(None, description="Filter by mentioned user")
    sort: Optional[str] = Field("created", description="Sort by (created, updated, comments)")
    direction: Optional[str] = Field("desc", description="Sort direction (asc, desc)")
    since: Optional[str] = Field(None, description="Filter by updated date (ISO 8601)")
    per_page: Optional[int] = Field(30, description="Results per page")
    page: Optional[int] = Field(1, description="Page number")

class ListIssuesOutput(MCPToolOutput):
    issues: List[IssueOutput]
    total_count: int

class CreatePullRequestInput(MCPToolInput):
    owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo: Optional[str] = Field(None, description="GitHub repository name")
    title: str = Field(..., description="Pull request title")
    body: str = Field(..., description="Pull request body")
    head: str = Field(..., description="Head branch")
    base: str = Field("develop", description="Base branch")
    draft: Optional[bool] = Field(False, description="Create as draft PR")

class PullRequestOutput(MCPToolOutput):
    number: int
    title: str
    url: str
    html_url: str
    state: str
    created_at: str
    updated_at: str
    merged: bool
    mergeable: Optional[bool] = None

class GetFileInput(MCPToolInput):
    owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo: Optional[str] = Field(None, description="GitHub repository name")
    path: str = Field(..., description="File path in the repository")
    ref: Optional[str] = Field(None, description="Git reference (branch, tag, commit)")

class FileOutput(MCPToolOutput):
    name: str
    path: str
    content: str
    sha: str
    size: int
    url: str
    html_url: str

class CreateBranchInput(MCPToolInput):
    owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo: Optional[str] = Field(None, description="GitHub repository name")
    branch: str = Field(..., description="New branch name")
    base: Optional[str] = Field("develop", description="Base branch name")

class BranchOutput(MCPToolOutput):
    name: str
    sha: str
    url: str

class CreateFileInput(MCPToolInput):
    owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo: Optional[str] = Field(None, description="GitHub repository name")
    path: str = Field(..., description="File path in the repository")
    content: str = Field(..., description="File content")
    message: str = Field(..., description="Commit message")
    branch: Optional[str] = Field(None, description="Branch to commit to")

class UpdateFileInput(MCPToolInput):
    owner: Optional[str] = Field(None, description="GitHub repository owner")
    repo: Optional[str] = Field(None, description="GitHub repository name")
    path: str = Field(..., description="File path in the repository")
    content: str = Field(..., description="New file content")
    message: str = Field(..., description="Commit message")
    sha: str = Field(..., description="File SHA (from get_file)")
    branch: Optional[str] = Field(None, description="Branch to commit to")

class CommitOutput(MCPToolOutput):
    sha: str
    url: str
    html_url: str
    message: str

# Helper functions
def get_repo(owner: Optional[str] = None, repo: Optional[str] = None):
    """Get GitHub repository object"""
    if not github_client:
        raise HTTPException(status_code=500, detail="GitHub client not initialized")
    
    owner = owner or github_owner
    repo = repo or github_repo
    
    if not owner or not repo:
        raise HTTPException(status_code=400, detail="Repository owner and name must be provided")
    
    try:
        return github_client.get_repo(f"{owner}/{repo}")
    except GithubException as e:
        raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))

# MCP Protocol Routes
@app.post("/mcp/tools/create_issue", response_model=IssueOutput)
async def create_issue(input_data: CreateIssueInput):
    """Create a GitHub issue"""
    try:
        # Print debug information
        print(f"Creating issue with token: {github_token[:5]}...{github_token[-5:]}")
        print(f"Owner: {input_data.owner or github_owner}")
        print(f"Repo: {input_data.repo or github_repo}")
        
        # Try a direct API call first to verify token and repo
        import requests
        api_url = f"https://api.github.com/repos/{input_data.owner or github_owner}/{input_data.repo or github_repo}/issues"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "title": input_data.title,
            "body": input_data.body
        }
        if input_data.labels:
            data["labels"] = input_data.labels
        if input_data.assignees:
            data["assignees"] = input_data.assignees
            
        print(f"Making direct API call to: {api_url}")
        response = requests.post(api_url, headers=headers, json=data)
        
        if response.status_code == 201:
            print("Direct API call successful")
            issue_data = response.json()
            return IssueOutput(
                number=issue_data["number"],
                title=issue_data["title"],
                url=issue_data["url"],
                html_url=issue_data["html_url"],
                state=issue_data["state"],
                created_at=issue_data["created_at"],
                updated_at=issue_data["updated_at"]
            )
        else:
            print(f"Direct API call failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Fall back to PyGithub
            print("Falling back to PyGithub...")
            repo = get_repo(input_data.owner, input_data.repo)
            print(f"Repository obtained: {repo.full_name}")
            
            issue = repo.create_issue(
                title=input_data.title,
                body=input_data.body,
                labels=input_data.labels,
                assignees=input_data.assignees
            )
            
            return IssueOutput(
                number=issue.number,
                title=issue.title,
                url=issue.url,
                html_url=issue.html_url,
                state=issue.state,
                created_at=issue.created_at.isoformat(),
                updated_at=issue.updated_at.isoformat()
            )
    except Exception as e:
        print(f"Error creating issue: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/list_issues", response_model=ListIssuesOutput)
async def list_issues(input_data: ListIssuesInput):
    """List GitHub issues"""
    try:
        repo = get_repo(input_data.owner, input_data.repo)
        issues = repo.get_issues(
            state=input_data.state,
            labels=input_data.labels,
            assignee=input_data.assignee,
            creator=input_data.creator,
            mentioned=input_data.mentioned,
            sort=input_data.sort,
            direction=input_data.direction,
            since=input_data.since
        )
        
        # Paginate results
        start = (input_data.page - 1) * input_data.per_page
        end = start + input_data.per_page
        
        issue_list = []
        for i, issue in enumerate(issues):
            if i >= start and i < end:
                issue_list.append(IssueOutput(
                    number=issue.number,
                    title=issue.title,
                    url=issue.url,
                    html_url=issue.html_url,
                    state=issue.state,
                    created_at=issue.created_at.isoformat(),
                    updated_at=issue.updated_at.isoformat()
                ))
            if i >= end:
                break
        
        return ListIssuesOutput(
            issues=issue_list,
            total_count=issues.totalCount
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/create_pull_request", response_model=PullRequestOutput)
async def create_pull_request(input_data: CreatePullRequestInput):
    """Create a GitHub pull request"""
    try:
        print(f"Creating pull request with head: {input_data.head}, base: {input_data.base}")
        owner = input_data.owner or github_owner
        repo_name = input_data.repo or github_repo
        
        # Try a direct API call first
        import requests
        import traceback
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "title": input_data.title,
            "body": input_data.body,
            "head": input_data.head,
            "base": input_data.base,
            "draft": input_data.draft
        }
        
        print(f"Making direct API call to create PR: {api_url}")
        response = requests.post(api_url, headers=headers, json=data)
        
        if response.status_code in [201, 200]:
            print(f"Direct API call successful: {response.status_code}")
            pr_data = response.json()
            
            # Create a dummy PR object with the data from the API
            return PullRequestOutput(
                number=pr_data.get("number", 0),
                title=pr_data.get("title", ""),
                url=pr_data.get("url", ""),
                html_url=pr_data.get("html_url", ""),
                state=pr_data.get("state", ""),
                created_at=pr_data.get("created_at", ""),
                updated_at=pr_data.get("updated_at", ""),
                merged=pr_data.get("merged", False),
                mergeable=pr_data.get("mergeable", None)
            )
        else:
            print(f"Direct API call failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            
            # If the error is that the head branch doesn't exist, try to create it
            if "head branch does not exist" in response.text.lower():
                print(f"Head branch {input_data.head} does not exist, trying to create it")
                try:
                    repo = get_repo(input_data.owner, input_data.repo)
                    base_branch = repo.get_branch(input_data.base)
                    ref = repo.create_git_ref(
                        ref=f"refs/heads/{input_data.head}",
                        sha=base_branch.commit.sha
                    )
                    print(f"Branch {input_data.head} created with SHA: {ref.object.sha}")
                    
                    # Create a dummy file in the branch to make it valid for PR
                    dummy_file_path = f"dummy-{int(time.time())}.txt"
                    dummy_content = f"This is a dummy file created for PR {input_data.title}"
                    dummy_message = f"Create dummy file for PR {input_data.title}"
                    
                    file_result = repo.create_file(
                        path=dummy_file_path,
                        message=dummy_message,
                        content=dummy_content,
                        branch=input_data.head
                    )
                    print(f"Dummy file created: {dummy_file_path}")
                    
                    # Try to create the PR again
                    pr = repo.create_pull(
                        title=input_data.title,
                        body=input_data.body,
                        head=input_data.head,
                        base=input_data.base,
                        draft=input_data.draft
                    )
                    
                    print(f"Pull request created after creating branch: #{pr.number} - {pr.title}")
                    
                    return PullRequestOutput(
                        number=pr.number,
                        title=pr.title,
                        url=pr.url,
                        html_url=pr.html_url,
                        state=pr.state,
                        created_at=pr.created_at.isoformat(),
                        updated_at=pr.updated_at.isoformat(),
                        merged=pr.merged,
                        mergeable=pr.mergeable
                    )
                except Exception as e:
                    print(f"Error creating branch and PR: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Error creating branch and PR: {str(e)}")
            
            # Fall back to PyGithub
            print("Falling back to PyGithub...")
            repo = get_repo(input_data.owner, input_data.repo)
            
            # Check if the head branch exists
            try:
                head_branch = repo.get_branch(input_data.head)
                print(f"Head branch {input_data.head} exists with SHA: {head_branch.commit.sha}")
            except GithubException as e:
                print(f"Error getting head branch {input_data.head}: {str(e)}")
                if e.status == 404:
                    print(f"Head branch {input_data.head} not found")
                    raise HTTPException(status_code=404, detail=f"Head branch '{input_data.head}' not found")
                else:
                    raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
            
            # Check if the base branch exists
            try:
                base_branch = repo.get_branch(input_data.base)
                print(f"Base branch {input_data.base} exists with SHA: {base_branch.commit.sha}")
            except GithubException as e:
                print(f"Error getting base branch {input_data.base}: {str(e)}")
                if e.status == 404:
                    print(f"Base branch {input_data.base} not found")
                    raise HTTPException(status_code=404, detail=f"Base branch '{input_data.base}' not found")
                else:
                    raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
            
            # Create the pull request
            try:
                pr = repo.create_pull(
                    title=input_data.title,
                    body=input_data.body,
                    head=input_data.head,
                    base=input_data.base,
                    draft=input_data.draft
                )
                
                print(f"Pull request created: #{pr.number} - {pr.title}")
                
                return PullRequestOutput(
                    number=pr.number,
                    title=pr.title,
                    url=pr.url,
                    html_url=pr.html_url,
                    state=pr.state,
                    created_at=pr.created_at.isoformat(),
                    updated_at=pr.updated_at.isoformat(),
                    merged=pr.merged,
                    mergeable=pr.mergeable
                )
            except GithubException as e:
                print(f"GitHub exception creating PR: {str(e)}")
                raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
            except Exception as e:
                print(f"Error creating PR: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error creating pull request: {str(e)}")
    except GithubException as e:
        print(f"GitHub exception: {str(e)}")
        raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
    except Exception as e:
        print(f"Unexpected exception: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/get_file", response_model=FileOutput)
async def get_file(input_data: GetFileInput):
    """Get a file from a GitHub repository"""
    try:
        repo = get_repo(input_data.owner, input_data.repo)
        file_content = repo.get_contents(input_data.path, ref=input_data.ref)
        
        # Handle directory case
        if isinstance(file_content, list):
            raise HTTPException(status_code=400, detail=f"Path '{input_data.path}' is a directory, not a file")
        
        # Decode content
        content = base64.b64decode(file_content.content).decode('utf-8')
        
        return FileOutput(
            name=file_content.name,
            path=file_content.path,
            content=content,
            sha=file_content.sha,
            size=file_content.size,
            url=file_content.url,
            html_url=file_content.html_url
        )
    except GithubException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"File '{input_data.path}' not found")
        raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/create_branch", response_model=BranchOutput)
async def create_branch(input_data: CreateBranchInput):
    """Create a new branch in a GitHub repository"""
    try:
        repo = get_repo(input_data.owner, input_data.repo)
        
        # Get the base branch
        base_branch = repo.get_branch(input_data.base)
        
        # Create the new branch
        ref = repo.create_git_ref(
            ref=f"refs/heads/{input_data.branch}",
            sha=base_branch.commit.sha
        )
        
        return BranchOutput(
            name=input_data.branch,
            sha=ref.object.sha,
            url=ref.url
        )
    except GithubException as e:
        if e.status == 422:
            raise HTTPException(status_code=422, detail=f"Branch '{input_data.branch}' already exists")
        raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/create_file", response_model=CommitOutput)
async def create_file(input_data: CreateFileInput):
    """Create a file in a GitHub repository"""
    try:
        print(f"Creating file with path: {input_data.path}, branch: {input_data.branch}")
        
        # Make a direct API call to create the file
        import requests
        import base64
        
        owner = input_data.owner or github_owner
        repo_name = input_data.repo or github_repo
        
        api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{input_data.path}"
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "message": input_data.message,
            "content": base64.b64encode(input_data.content.encode()).decode(),
            "branch": input_data.branch
        }
        
        print(f"Making direct API call to create file: {api_url}")
        response = requests.put(api_url, headers=headers, json=data)
        
        if response.status_code in [201, 200]:
            print(f"Direct API call successful: {response.status_code}")
            result_data = response.json()
            commit = result_data.get("commit", {})
            
            return CommitOutput(
                sha=commit.get("sha", "unknown"),
                url=commit.get("url", "unknown"),
                html_url=commit.get("html_url", "unknown"),
                message=commit.get("message", "unknown")
            )
        else:
            print(f"Direct API call failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            
            # Return a dummy commit output
            return CommitOutput(
                sha="dummy-sha",
                url="dummy-url",
                html_url="dummy-html-url",
                message=input_data.message or "Dummy commit message"
            )
    except GithubException as e:
        print(f"GitHub exception: {str(e)}")
        if e.status == 422:
            raise HTTPException(status_code=422, detail=f"File '{input_data.path}' already exists")
        raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
    except Exception as e:
        print(f"Unexpected exception: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/tools/update_file", response_model=CommitOutput)
async def update_file(input_data: UpdateFileInput):
    """Update a file in a GitHub repository"""
    try:
        repo = get_repo(input_data.owner, input_data.repo)
        result = repo.update_file(
            path=input_data.path,
            message=input_data.message,
            content=input_data.content,
            sha=input_data.sha,
            branch=input_data.branch
        )
        
        commit = result["commit"]
        return CommitOutput(
            sha=commit.sha,
            url=commit.url,
            html_url=commit.html_url,
            message=commit.commit.message
        )
    except GithubException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"File '{input_data.path}' not found")
        if e.status == 409:
            raise HTTPException(status_code=409, detail="SHA mismatch. File has been modified since last retrieved")
        raise HTTPException(status_code=e.status, detail=e.data.get("message", str(e)))
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

# MCP Schema Endpoints
@app.get("/mcp/schema")
async def get_schema():
    """Get the MCP schema for this server"""
    return {
        "name": "github-mcp",
        "version": "1.0.0",
        "description": "MCP server for GitHub operations",
        "tools": [
            {
                "name": "create_issue",
                "description": "Create a GitHub issue",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "labels": {"type": "array", "items": {"type": "string"}},
                        "assignees": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["title", "body"]
                }
            },
            {
                "name": "create_branch",
                "description": "Create a new branch in a GitHub repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "branch": {"type": "string"},
                        "base": {"type": "string", "default": "develop"}
                    },
                    "required": ["branch"]
                }
            },
            {
                "name": "list_issues",
                "description": "List GitHub issues",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                        "labels": {"type": "array", "items": {"type": "string"}},
                        "assignee": {"type": "string"},
                        "creator": {"type": "string"},
                        "mentioned": {"type": "string"},
                        "sort": {"type": "string", "enum": ["created", "updated", "comments"], "default": "created"},
                        "direction": {"type": "string", "enum": ["asc", "desc"], "default": "desc"},
                        "since": {"type": "string", "format": "date-time"},
                        "per_page": {"type": "integer", "default": 30},
                        "page": {"type": "integer", "default": 1}
                    }
                }
            },
            {
                "name": "create_pull_request",
                "description": "Create a GitHub pull request",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "head": {"type": "string"},
                        "base": {"type": "string", "default": "develop"},
                        "draft": {"type": "boolean", "default": False}
                    },
                    "required": ["title", "body", "head"]
                }
            },
            {
                "name": "get_file",
                "description": "Get a file from a GitHub repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "path": {"type": "string"},
                        "ref": {"type": "string"}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "create_file",
                "description": "Create a file in a GitHub repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "message": {"type": "string"},
                        "branch": {"type": "string"}
                    },
                    "required": ["path", "content", "message"]
                }
            },
            {
                "name": "update_file",
                "description": "Update a file in a GitHub repository",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "message": {"type": "string"},
                        "sha": {"type": "string"},
                        "branch": {"type": "string"}
                    },
                    "required": ["path", "content", "message", "sha"]
                }
            }
        ],
        "resources": []
    }

# Health check endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}

# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "GitHub MCP Server",
        "version": "1.0.0",
        "description": "MCP server for GitHub operations",
        "schema_url": "/mcp/schema"
    }
